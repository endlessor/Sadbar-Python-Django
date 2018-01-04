from dateutil import parser
import json
import re
import os
import ssl
import logging
import urllib2
from urlparse import urlparse
from socket import gethostbyname
from socket import error as SocketError
from random import getrandbits

from rest_framework import schemas, status
from rest_framework.response import Response
from rest_framework.decorators import (api_view, renderer_classes, list_route,
                                       detail_route)
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.views import APIView
from rest_framework_jwt.serializers import JSONWebTokenSerializer
from rest_framework_jwt.views import JSONWebTokenAPIView
from rest_framework_swagger.renderers import OpenAPIRenderer, SwaggerUIRenderer
from dynamic_rest.viewsets import DynamicModelViewSet

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import EmailMessage
from django.core.mail.backends.smtp import EmailBackend
from django.db import transaction

from api.serializers import *
from api.embedded_serializers import *
from api.oauth_utils import (process_gmail_message_headers,
                             process_gmail_message_body)
from api.utils import (create_target_list_from_csv, decode_quopri,
                       retrieve_target_from_mixed_data)
from client import google_api
from client.helpers import replace_shortcodes
from client.models import *
from client.tasks import generateContent
from client.xml_report import create_xml_report_response
from page_parser.tasks import parse_page


logger = logging.getLogger(__name__)


class VersionableDynamicModelViewSet(DynamicModelViewSet):

    @property
    def serializer_class(self):
        return self.get_serializer_class()


# Reference: https://github.com/marcgibbons/django-rest-swagger
@api_view()
@renderer_classes([OpenAPIRenderer, SwaggerUIRenderer])
def schema_view(request, *args, **kwargs):
    generator = schemas.SchemaGenerator(title='Sandbar API')
    return Response(generator.get_schema(request=request))


class SiteSettingsViewSet(VersionableDynamicModelViewSet):
    model = SiteSettings
    queryset = SiteSettings.objects.all()
    serializer_class = SiteSettingsSerializer

    def get_serializer_class(self):
        if self.request.version == 'v1':
            return SiteSettingsSerializer
        return EmbeddedSiteSettingsSerializer


class SlackHookViewSet(VersionableDynamicModelViewSet):
    model = SlackHook
    queryset = SlackHook.objects.all()
    serializer_class = SlackHookSerializer

    def get_serializer_class(self):
        if self.request.version == 'v1':
            return SlackHookSerializer
        return EmbeddedSlackHookSerializer


class UserViewSet(VersionableDynamicModelViewSet):
    model = User
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def get_serializer_class(self):
        if self.request.version == 'v1':
            return UserSerializer
        return EmbeddedUserSerializer


class ProfileViewSet(VersionableDynamicModelViewSet):
    model = Profile
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer

    def get_serializer_class(self):
        if self.request.version == 'v1':
            return ProfileSerializer
        return EmbeddedProfileSerializer

    @list_route()
    def choices(self, request, *args, **kwargs):
        timezones = [choice[0] for choice in Profile.tz_list]
        return Response({'timezone': timezones})


class EmailServerViewSet(VersionableDynamicModelViewSet):
    model = EmailServer
    queryset = EmailServer.objects.all()
    serializer_class = EmailServerSerializer

    def get_serializer_class(self):
        if self.request.version == 'v1':
            return EmailServerSerializer
        return EmbeddedEmailServerSerializer

    def destroy(self, request, *args, **kwargs):
        try:
            response = super(EmailServerViewSet, self).destroy(request,
                                                               *args,
                                                               **kwargs)
        except DependentEngagementError as error:
            obj = self.get_object()
            message = '{}: "{}"'.format(obj.id, obj.__unicode__())
            message += (' could not be deleted because the following active'
                        ' engagements depend upon it:')
            for each_id in error.engagements:
                engagement = Engagement.objects.get(id=each_id)
                message += '\n    {}: {}'.format(each_id, engagement.name)
            logger.info('[ - ] EmailServerViewSet DELETE blocked: {}'
                        ''.format(message))
            response = Response({'dependent_engagements': error.engagements},
                                status=status.HTTP_409_CONFLICT)
        return response


class PhishingDomainViewSet(VersionableDynamicModelViewSet):
    model = PhishingDomain
    queryset = PhishingDomain.objects.all()
    serializer_class = PhishingDomainSerializer

    def get_serializer_class(self):
        if self.request.version == 'v1':
            return PhishingDomainSerializer
        return EmbeddedPhishingDomainSerializer

    def destroy(self, request, *args, **kwargs):
        try:
            response = super(PhishingDomainViewSet, self).destroy(request,
                                                                  *args,
                                                                  **kwargs)
        except DependentEngagementError as error:
            obj = self.get_object()
            message = '{}: "{}"'.format(obj.id, obj.__unicode__())
            message += (' could not be deleted because the following active'
                        ' engagements depend upon it:')
            for each_id in error.engagements:
                engagement = Engagement.objects.get(id=each_id)
                message += '\n    {}: {}'.format(each_id, engagement.name)
            logger.info('[ - ] PhishingDomainViewSet DELETE blocked: {}'
                        ''.format(message))
            response = Response({'dependent_engagements': error.engagements},
                                status=status.HTTP_409_CONFLICT)
        return response

    @list_route()
    def choices(self, request, *args, **kwargs):
        return Response({'protocol': PhishingDomain.PROTOCOLS})


class ScraperUserAgentViewSet(VersionableDynamicModelViewSet):
    model = ScraperUserAgent
    queryset = ScraperUserAgent.objects.all()
    serializer_class = ScraperUserAgentSerializer

    def get_serializer_class(self):
        if self.request.version == 'v1':
            return ScraperUserAgentSerializer
        return EmbeddedScraperUserAgentSerializer


class ScheduleViewSet(VersionableDynamicModelViewSet):
    model = Schedule
    queryset = Schedule.objects.all()
    serializer_class = ScheduleSerializer

    def get_serializer_class(self):
        if self.request.version == 'v1':
            return ScheduleSerializer
        return EmbeddedScheduleSerializer

    def destroy(self, request, *args, **kwargs):
        try:
            response = super(ScheduleViewSet, self).destroy(request,
                                                            *args,
                                                            **kwargs)
        except DependentEngagementError as error:
            obj = self.get_object()
            message = '{}'.format(obj.__unicode__())
            message += (' could not be deleted because the following active'
                        ' engagements depend upon it:')
            for each_id in error.engagements:
                engagement = Engagement.objects.get(id=each_id)
                message += '\n    {}: {}'.format(each_id, engagement.name)
            logger.info('[ - ] ScheduleViewSet DELETE blocked: {}'
                        ''.format(message))
            response = Response({'dependent_engagements': error.engagements},
                                status=status.HTTP_409_CONFLICT)
        return response

    @detail_route(methods=['post'], url_path='schedule-preview')
    def preview(self, request, *args, **kwargs):

        schedule = self.model.objects.get(id=kwargs['pk'])
        unparsed_start_date = request.data.get('start_date', None)
        unparsed_start_time = request.data.get('start_time', None)

        try:
            number_to_schedule = int(request.data.get('number_to_schedule', None))
        except:
            raise DRFValidationError({'number_to_schedule': ['number_to_schedule must be an integer']})

        try:
            start_date = parser.parse(unparsed_start_date)
        except:
            raise DRFValidationError({'start_date': ['start_date must use the format YYYY-MM-DD']})
        try:
            hours, minutes, seconds = unparsed_start_time.split(':')
        except:
            raise DRFValidationError({'start_time': ['start_time must use the format HH:MM:SS']})
        try:
            start_datetime = start_date + dj_tz.timedelta(hours=int(hours), minutes=int(minutes), seconds=int(seconds))
        except:
            raise DRFValidationError({'start_date': ['Error combining start_date and start_time'],
                                      'start_time': ['Error combining start_date and start_time']})

        generated_times = schedule.calculate_sending_times(start_datetime, number_to_schedule)
        stop_datetime = generated_times[-1]
        sending_duration = str(stop_datetime - start_datetime)

        return Response({
            'number_scheduled': number_to_schedule,
            'start_datetime': start_datetime,
            'stop_datetime': stop_datetime,
            'sending_duration': sending_duration,
            'schedule_preview': generated_times
        })


class ScheduleWindowViewSet(VersionableDynamicModelViewSet):
    model = ScheduleWindow
    queryset = ScheduleWindow.objects.all()
    serializer_class = ScheduleWindowSerializer

    def get_serializer_class(self):
        if self.request.version == 'v1':
            return ScheduleWindowSerializer
        return EmbeddedScheduleWindowSerializer

    def destroy(self, request, *args, **kwargs):
        try:
            response = super(ScheduleWindowViewSet, self).destroy(request,
                                                                  *args,
                                                                  **kwargs)
        except DependentEngagementError as error:
            obj = self.get_object()
            message = '{}'.format(obj.__unicode__())
            message += (' could not be deleted because the following active'
                        ' engagements depend upon it:')
            for each_id in error.engagements:
                engagement = Engagement.objects.get(id=each_id)
                message += '\n    {}: {}'.format(each_id, engagement.name)
            logger.info('[ - ] ScheduleWindowViewSet DELETE blocked: {}'
                        ''.format(message))
            response = Response({'dependent_engagements': error.engagements},
                                status=status.HTTP_409_CONFLICT)
        return response

    @list_route()
    def choices(self, request, *args, **kwargs):
        return Response({'day_of_the_week': ScheduleWindow.WEEKDAY_CHOICES})


class LandingPageViewSet(VersionableDynamicModelViewSet):
    model = LandingPage
    queryset = LandingPage.objects.filter(is_redirect_page=False)
    serializer_class = LandingPageSerializer

    def get_serializer_class(self):
        if self.request.version == 'v1':
            return LandingPageSerializer
        return EmbeddedLandingPageSerializer

    def create(self, request, *args, **kwargs):
        commit = request.data.get('commit')
        source = request.data.get('source', None)
        refetch = request.data.get('refetch', None)
        if source is not None:
            request.data.pop('source')
        if refetch is not None:
            request.data.pop('refetch')

        resp = super(LandingPageViewSet, self).create(request, *args, **kwargs)

        if commit:
            landing_page_id = resp.data['landing_page']['id']
            landing_page = LandingPage.objects.get(id=landing_page_id)

            if landing_page.page_type == 'page':
                landing_page.path = None
                landing_page.status = 2
                landing_page.save()
                try:
                    parse_page.delay(landing_page)
                except SocketError:
                    # To inform the user that Sandbar can't connect to Celery,
                    # keep the status set to the refresh animation.
                    pass

            elif source and landing_page.page_type == 'manual':
                filename = '%032x.html' % getrandbits(128)
                dirname = '{}-{}'.format(landing_page.id,
                                         landing_page.date_created.strftime('%s'))
                page_path = os.path.join('assets', 'landing-pages',
                                         dirname, 'html', filename)
                if not os.path.exists(os.path.dirname(page_path)):
                    os.makedirs(os.path.dirname(page_path))
                with open(page_path, 'w') as file:
                    file.write(source.encode('utf-8'))
                landing_page.path = page_path
                landing_page.status = 1
                landing_page.save()

        return resp

    def update(self, request, *args, **kwargs):
        commit = request.data.get('commit')
        source = request.data.get('source', None)
        refetch = request.data.get('refetch', None)
        if source is not None:
            request.data.pop('source')
        if refetch is not None:
            request.data.pop('refetch')

        if commit:
            landing_page_id = kwargs.get('pk')
            # In order to know whether or not to request a re-parse of the
            # page, we need to know certain pre-save values.
            old_landing_page = LandingPage.objects.get(id=landing_page_id)
            old_scraper_user_agent = old_landing_page.scraper_user_agent
            old_url = old_landing_page.url

            resp = super(LandingPageViewSet, self).update(request, *args, **kwargs)

            landing_page = LandingPage.objects.get(id=landing_page_id)

            is_changed = False
            if refetch and landing_page.page_type == 'page':
                is_changed = True
            if old_url != landing_page.url:
                is_changed = True
            if not landing_page.path:
                is_changed = True
            if old_scraper_user_agent != landing_page.scraper_user_agent:
                is_changed = True

            if landing_page.page_type == 'page':
                if source and not is_changed:
                    with open(landing_page.path, 'w') as file:
                        file.write(source.encode('utf-8'))
                elif is_changed:
                    landing_page.path = None
                    landing_page.status = 2
                    landing_page.save()
                    try:
                        parse_page.delay(landing_page)
                    except SocketError:
                        # To inform the user that Sandbar can't connect to
                        # Celery, keep the status set to the refresh animation.
                        pass

            elif source and landing_page.page_type == 'manual':
                if landing_page.path is None:
                    filename = '%032x.html' % getrandbits(128)
                    dirname = '{}-{}'.format(landing_page.id,
                                             landing_page.date_created.strftime('%s'))
                    page_path = os.path.join('assets', 'landing-pages',
                                             dirname, 'html', filename)
                else:
                    page_path = landing_page.path
                if not os.path.exists(os.path.dirname(page_path)):
                    os.makedirs(os.path.dirname(page_path))
                with open(page_path, 'w') as file:
                    file.write(source.encode('utf-8'))
                landing_page.path = page_path
                landing_page.status = 1
                landing_page.save()

            return resp

        else:
            resp = super(LandingPageViewSet, self).update(request, *args, **kwargs)
            return resp

    def destroy(self, request, *args, **kwargs):
        try:
            response = super(LandingPageViewSet, self).destroy(request,
                                                               *args,
                                                               **kwargs)
        except DependentEngagementError as error:
            obj = self.get_object()
            message = '{}: "{}"'.format(obj.id, obj.__unicode__())
            message += (' could not be deleted because the following active'
                        ' engagements depend upon it:')
            for each_id in error.engagements:
                engagement = Engagement.objects.get(id=each_id)
                message += '\n    {}: {}'.format(each_id, engagement.name)
            logger.info('[ - ] LandingPageViewSet DELETE blocked: {}'
                        ''.format(message))
            response = Response({'dependent_engagements': error.engagements},
                                status=status.HTTP_409_CONFLICT)
        return response

    @list_route()
    def choices(self, request, *args, **kwargs):
        # When the old UI is fully deprecated, 'status' should be pointed at
        # LandingPage.STATUSES.
        return Response({'status': ((1, 'Success'),
                                    (2, 'In progress'),
                                    (3, 'Failure')),
                         'page_type': LandingPage.PAGE_TYPES})


class RedirectPageViewSet(VersionableDynamicModelViewSet):
    model = LandingPage
    queryset = LandingPage.objects.filter(is_redirect_page=True)
    serializer_class = RedirectPageSerializer

    def get_serializer_class(self):
        if self.request.version == 'v1':
            return RedirectPageSerializer
        return EmbeddedRedirectPageSerializer

    def create(self, request, *args, **kwargs):
        commit = request.data.get('commit')
        source = request.data.get('source', None)
        refetch = request.data.get('refetch', None)
        if source is not None:
            request.data.pop('source')
        if refetch is not None:
            request.data.pop('refetch')

        resp = super(RedirectPageViewSet, self).create(request, *args, **kwargs)

        if commit:
            redirect_page_id = resp.data['landing_page']['id']
            redirect_page = LandingPage.objects.get(id=redirect_page_id)

            if redirect_page.page_type == 'page':
                redirect_page.path = None
                redirect_page.status = 2
                redirect_page.save()
                try:
                    parse_page.delay(redirect_page)
                except SocketError:
                    # The current way to inform the user that Celery isn't
                    # running is to keep the refresh animation (status 2).
                    pass

            elif source and redirect_page.page_type == 'manual':
                filename = '%032x.html' % getrandbits(128)
                dirname = '{}-{}'.format(redirect_page.id,
                                         redirect_page.date_created.strftime('%s'))
                page_path = os.path.join('assets', 'redirect-pages',
                                         dirname, 'html', filename)
                if not os.path.exists(os.path.dirname(page_path)):
                    os.makedirs(os.path.dirname(page_path))
                with open(page_path, 'w') as file:
                    file.write(source.encode('utf-8'))
                redirect_page.path = page_path
                redirect_page.status = 1
                redirect_page.save()

            elif redirect_page.page_type == 'url':
                redirect_page.path = None
                redirect_page.save()

        return resp

    def update(self, request, *args, **kwargs):
        commit = request.data.get('commit')
        source = request.data.get('source', None)
        refetch = request.data.get('refetch', None)
        if source is not None:
            request.data.pop('source')
        if refetch is not None:
            request.data.pop('refetch')

        if commit:
            redirect_page_id = kwargs.get('pk')
            # In order to know whether or not to request a re-parse of the
            # page, we need to know certain pre-save values.
            old_redirect_page = LandingPage.objects.get(id=redirect_page_id)
            old_scraper_user_agent = old_redirect_page.scraper_user_agent
            old_url = old_redirect_page.url

            resp = super(RedirectPageViewSet, self).update(request, *args, **kwargs)

            redirect_page = LandingPage.objects.get(id=redirect_page_id)

            is_changed = False
            if refetch and redirect_page.page_type == 'page':
                is_changed = True
            if old_url != redirect_page.url:
                is_changed = True
            if not redirect_page.path:
                is_changed = True
            if old_scraper_user_agent != redirect_page.scraper_user_agent:
                is_changed = True

            if redirect_page.page_type == 'page':
                if source and not is_changed:
                    with open(redirect_page.path, 'w') as file:
                        file.write(source.encode('utf-8'))
                elif is_changed:
                    redirect_page.path = None
                    redirect_page.status = 2
                    redirect_page.save()
                    try:
                        parse_page.delay(redirect_page)
                    except SocketError:
                        # The current way to inform the user that Celery isn't
                        # running is to keep the refresh animation (status 2).
                        pass

            elif source and redirect_page.page_type == 'manual':
                if redirect_page.path is None:
                    filename = '%032x.html' % getrandbits(128)
                    dirname = '{}-{}'.format(redirect_page.id,
                                             redirect_page.date_created.strftime('%s'))
                    page_path = os.path.join('assets', 'redirect-pages',
                                             dirname, 'html', filename)
                else:
                    page_path = redirect_page.path
                if not os.path.exists(os.path.dirname(page_path)):
                    os.makedirs(os.path.dirname(page_path))
                with open(page_path, 'w') as file:
                    file.write(source.encode('utf-8'))
                redirect_page.path = page_path
                redirect_page.status = 1
                redirect_page.save()

            elif redirect_page.page_type == 'url':
                redirect_page.path = None
                redirect_page.save()

            return resp

        else:
            resp = super(RedirectPageViewSet, self).update(request, *args, **kwargs)
            return resp

    def destroy(self, request, *args, **kwargs):
        try:
            response = super(RedirectPageViewSet, self).destroy(request,
                                                                *args,
                                                                **kwargs)
        except DependentEngagementError as error:
            obj = self.get_object()
            message = '{}: "{}"'.format(obj.id, obj.__unicode__())
            message += (' could not be deleted because the following active'
                        ' engagements depend upon it:')
            for each_id in error.engagements:
                engagement = Engagement.objects.get(id=each_id)
                message += '\n    {}: {}'.format(each_id, engagement.name)
            logger.info('[ - ] RedirectPageViewSet DELETE blocked: {}'
                        ''.format(message))
            response = Response({'dependent_engagements': error.engagements},
                                status=status.HTTP_409_CONFLICT)
        return response

    @list_route()
    def choices(self, request, *args, **kwargs):
        return Response({'status': ((1, 'Success'),
                                    (2, 'In progress'),
                                    (3, 'Failure')),
                         'page_type': LandingPage.PAGE_TYPES})


class EmailTemplateViewSet(VersionableDynamicModelViewSet):
    model = EmailTemplate
    queryset = EmailTemplate.objects.all()
    serializer_class = EmailTemplateSerializer

    def get_serializer_class(self):
        if self.request.version == 'v1':
            return EmailTemplateSerializer
        return EmbeddedEmailTemplateSerializer

    # NOTE: The serializer doesn't have target_list_view, as client/views does
    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        decode = request.data.get('decode', False)
        if decode is True:
            return Response(decode_quopri(request.data.get('template')))
        return super(EmailTemplateViewSet, self).create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        decode = request.data.get('decode', False)
        if decode is True:
            return Response(decode_quopri(request.data.get('template')))
        return super(EmailTemplateViewSet, self).update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        try:
            response = super(EmailTemplateViewSet, self).destroy(request,
                                                                 *args,
                                                                 **kwargs)
        except DependentEngagementError as error:
            obj = self.get_object()
            message = '{}: "{}"'.format(obj.id, obj.__unicode__())
            message += (' could not be deleted because the following active'
                        ' engagements depend upon it:')
            for each_id in error.engagements:
                engagement = Engagement.objects.get(id=each_id)
                message += '\n    {}: {}'.format(each_id, engagement.name)
            logger.info('[ - ] EmailTemplateViewSet DELETE blocked: {}'
                        ''.format(message))
            response = Response({'dependent_engagements': error.engagements},
                                status=status.HTTP_409_CONFLICT)
        return response


class ClientViewSet(VersionableDynamicModelViewSet):
    model = Client
    queryset = Client.objects.all()
    serializer_class = ClientSerializer

    def get_serializer_class(self):
        if self.request.version == 'v1':
            return ClientSerializer
        return EmbeddedClientSerializer

    @list_route()
    def choices(self, request, *args, **kwargs):
        default_time_zones = [choice[0] for choice in Client.tz_list]
        return Response({'default_time_zone': default_time_zones})

    @detail_route(methods=['get'], url_path='xml-report')
    def xml_report(self, request, *args, **kwargs):
        return create_xml_report_response(client_id=kwargs.get('pk'))


class CampaignViewSet(VersionableDynamicModelViewSet):
    model = Campaign
    queryset = Campaign.objects.all()
    serializer_class = CampaignSerializer

    def get_serializer_class(self):
        if self.request.version == 'v1':
            return CampaignSerializer
        return EmbeddedCampaignSerializer

    @detail_route(methods=['get'], url_path='xml-report')
    def xml_report(self, request, *args, **kwargs):
        return create_xml_report_response(campaign_id=kwargs.get('pk'))


# ResultEvents may not be created, updated, or deleted through the API.
class ResultEventViewSet(VersionableDynamicModelViewSet):
    model = ResultEvent
    queryset = ResultEvent.objects.all()
    serializer_class = ResultEventSerializer
    http_method_names = ('get', 'head', 'options')

    def get_serializer_class(self):
        if self.request.version == 'v1':
            return ResultEventSerializer
        return EmbeddedResultEventSerializer

    @list_route()
    def choices(self, request, *args, **kwargs):
        return Response({'event_type': ResultEvent.CHOICES})


class TargetDatumViewSet(VersionableDynamicModelViewSet):
    model = TargetDatum
    queryset = TargetDatum.objects.all()
    serializer_class = TargetDatumSerializer

    def get_serializer_class(self):
        if self.request.version == 'v1':
            return TargetDatumSerializer
        return EmbeddedTargetDatumSerializer


class TargetViewSet(VersionableDynamicModelViewSet):
    model = Target
    queryset = Target.objects.all()
    serializer_class = TargetSerializer

    def get_serializer_class(self):
        if self.request.version == 'v1':
            return TargetSerializer
        return EmbeddedTargetSerializer

    @list_route()
    def choices(self, request, *args, **kwargs):
        timezones = [choice[0] for choice in Target.tz_list]
        return Response({'timezone': timezones})


class TargetListViewSet(VersionableDynamicModelViewSet):
    model = TargetList
    queryset = TargetList.objects.all()
    serializer_class = TargetListSerializer

    def get_serializer_class(self):
        if self.request.version == 'v1':
            return TargetListSerializer
        return EmbeddedTargetListSerializer

    @list_route(methods=['post'], url_path='schedule-preview')
    def preview(self, request, *args, **kwargs):

        # The reason I made this a target-lists route is because the logic is
        # heavily oriented towards unpacking target lists. It could be made
        # optional, but it might be better to implement different functionality
        # via different endpoints.

        schedule_id = request.data.get('schedule_id', None)
        unparsed_start_date = request.data.get('start_date', None)
        unparsed_start_time = request.data.get('start_time', None)

        try:
            target_list_ids = json.loads(request.data.get('target_list_ids', None))
            assert isinstance(target_list_ids, list), 'target_list_ids != list'
        except:
            raise DRFValidationError({'target_list_ids': ['target_list_ids must be a JSON list']})

        try:
            start_date = parser.parse(unparsed_start_date)
        except:
            raise DRFValidationError({'start_date': ['start_date must use the format YYYY-MM-DD']})
        try:
            hours, minutes, seconds = unparsed_start_time.split(':')
        except:
            raise DRFValidationError({'start_time': ['start_time must use the format HH:MM:SS']})
        try:
            start_datetime = start_date + dj_tz.timedelta(hours=int(hours), minutes=int(minutes), seconds=int(seconds))
        except:
            raise DRFValidationError({'start_date': ['Error combining start_date and start_time'],
                                      'start_time': ['Error combining start_date and start_time']})

        schedule = Schedule.objects.get(id=schedule_id)

        targets_to_schedule = list()
        for target_list in TargetList.objects.filter(id__in=target_list_ids).order_by('id'):
            for target in target_list.target.order_by('id'):
                targets_to_schedule.append(target)

        number_to_schedule = len(targets_to_schedule)
        generated_times = schedule.calculate_sending_times(start_datetime, number_to_schedule)

        schedule_preview = list()
        for index, target in enumerate(targets_to_schedule):
            schedule_preview.append({
                'id': str(target.id),
                'send_at': str(generated_times[index]),
                'email': str(target.email)

            })

        stop_datetime = generated_times[-1]
        sending_duration = str(stop_datetime - start_datetime)

        return Response({
            'number_scheduled': number_to_schedule,
            'start_datetime': start_datetime,
            'stop_datetime': stop_datetime,
            'sending_duration': sending_duration,
            'schedule_preview': schedule_preview
        })


# Note: VectorEmails are currently not created or updated via the Sandbar UI.
# These methods will only be available after the VE customization patch.
class VectorEmailViewSet(VersionableDynamicModelViewSet):
    model = VectorEmail
    queryset = VectorEmail.objects.all()
    serializer_class = VectorEmailSerializer
    http_method_names = ('get', 'delete', 'head', 'options')

    def get_serializer_class(self):
        if self.request.version == 'v1':
            return VectorEmailSerializer
        return EmbeddedVectorEmailSerializer

    @list_route()
    def choices(self, request, *args, **kwargs):
        return Response({'state': VectorEmail.STATE_CHOICES})


class EngagementViewSet(VersionableDynamicModelViewSet):
    model = Engagement
    queryset = Engagement.objects.exclude(oauthengagement=OAuthEngagement.objects.all())
    serializer_class = EngagementSerializer

    def get_serializer_class(self):
        if self.request.version == 'v1':
            return EngagementSerializer
        return EmbeddedEngagementSerializer

    def update(self, request, *args, **kwargs):
        new_state = request.data.get('state', None)
        commit = request.data.get('commit', False)

        if new_state is not None:
            instance = self.get_object()

            if new_state not in Engagement.ALL_STATES:
                raise DRFValidationError({'state': 'State must be one of these'
                                          ' values: {}'
                                          ''.format(Engagement.ALL_STATES)})

            # If the state is not being changed, other fields may be updated.
            if new_state == instance.state:
                pass

            elif commit is False or len(instance.missing_dependencies) > 0:
                return Response(
                    {'non_field_errors':
                        {'missing_dependencies': instance.missing_dependencies}
                    },
                    status=status.HTTP_424_FAILED_DEPENDENCY
                )

            # Changing an Engagement's state should prevent changing other
            # fields in the same request.
            else:
                instance.set_state(int(new_state))
                serializer = self.get_serializer(instance)
                return Response(serializer.data)

        return super(EngagementViewSet, self).update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        engagement_id = kwargs.get('pk')
        try:
            if Engagement.objects.get(id=engagement_id).state == 1:
                return Response({'non_field_errors': 'Engagement {} is in'
                                 ' progress and may not be deleted.'
                                 ''.format(engagement_id)},
                                status=status.HTTP_409_CONFLICT)
        except Engagement.DoesNotExist:
            pass
        return super(EngagementViewSet, self).destroy(request, *args, **kwargs)

    @list_route()
    def choices(self, request, *args, **kwargs):
        return Response({'state': Engagement.STATE_CHOICES,
                         'start_type': Engagement.START_TYPES})

    @detail_route(methods=['get'], url_path='xml-report')
    def xml_report(self, request, *args, **kwargs):
        return create_xml_report_response(engagement_id=kwargs.get('pk'))


class OAuthEngagementViewSet(VersionableDynamicModelViewSet):
    model = OAuthEngagement
    queryset = OAuthEngagement.objects.all()
    serializer_class = OAuthEngagementSerializer

    def get_serializer_class(self):
        if self.request.version == 'v1':
            return OAuthEngagementSerializer
        return EmbeddedOAuthEngagementSerializer

    def update(self, request, *args, **kwargs):
        new_state = request.data.get('state', None)
        commit = request.data.get('commit', False)

        if new_state is not None:
            instance = self.get_object()

            if new_state not in OAuthEngagement.ALL_STATES:
                raise DRFValidationError({'state': 'State must be one of these'
                                          ' values: {}'
                                          ''.format(OAuthEngagement.ALL_STATES)})

            # If the state is not being changed, other fields may be updated.
            if new_state == instance.state:
                pass

            elif commit is False or len(instance.missing_dependencies) > 0:
                return Response(
                    {'non_field_errors':
                        {'missing_dependencies': instance.missing_dependencies}
                    },
                    status=status.HTTP_424_FAILED_DEPENDENCY
                )

            # Changing an OAuthEngagement's state should prevent changing other
            # fields in the same request.
            else:
                instance.set_state(int(new_state))
                serializer = self.get_serializer(instance)
                return Response(serializer.data)

        return super(OAuthEngagementViewSet, self).update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        oauth_engagement_id = kwargs.get('pk')
        try:
            if OAuthEngagement.objects.get(id=oauth_engagement_id).state == 1:
                return Response({'non_field_errors': 'OAuthEngagement {} is in'
                                 ' progress and may not be deleted.'
                                 ''.format(oauth_engagement_id)},
                                status=status.HTTP_409_CONFLICT)
        except OAuthEngagement.DoesNotExist:
            pass
        return super(OAuthEngagementViewSet, self).destroy(request, *args,
                                                           **kwargs)

    @list_route()
    def choices(self, request, *args, **kwargs):
        return Response({'state': OAuthEngagement.STATE_CHOICES,
                         'start_type': OAuthEngagement.START_TYPES})


class OAuthConsumerViewSet(VersionableDynamicModelViewSet):
    model = OAuthConsumer
    queryset = OAuthConsumer.objects.all()
    serializer_class = OAuthConsumerSerializer

    def get_serializer_class(self):
        if self.request.version == 'v1':
            return OAuthConsumerSerializer
        return EmbeddedOAuthConsumerSerializer


# OAuthResults can't be created or updated via the API; that happens on grant.
class OAuthResultViewSet(VersionableDynamicModelViewSet):
    model = OAuthResult
    queryset = OAuthResult.objects.all()
    serializer_class = OAuthResultSerializer
    http_method_names = ('get', 'delete', 'head', 'options')

    def get_serializer_class(self):
        if self.request.version == 'v1':
            return OAuthResultSerializer
        return EmbeddedOAuthResultSerializer


# Plunder is similar to OAuthResult in that they're created and updated
# internally and not through the API.
class PlunderViewSet(VersionableDynamicModelViewSet):
    model = Plunder
    queryset = Plunder.objects.all()
    serializer_class = PlunderSerializer
    http_method_names = ('get', 'delete', 'head', 'options')

    def get_serializer_class(self):
        if self.request.version == 'v1':
            return PlunderSerializer
        return EmbeddedPlunderSerializer


class ShoalScrapeCredsViewSet(VersionableDynamicModelViewSet):
    model = ShoalScrapeCreds
    queryset = ShoalScrapeCreds.objects.all()
    serializer_class = ShoalScrapeCredsSerializer

    def get_serializer_class(self):
        if self.request.version == 'v1':
            return ShoalScrapeCredsSerializer
        return EmbeddedShoalScrapeCredsSerializer


# UNFINISHED: POST, PUT, PATCH
class ShoalScrapeTaskViewSet(VersionableDynamicModelViewSet):
    model = ShoalScrapeTask
    queryset = ShoalScrapeTask.objects.all()
    serializer_class = ShoalScrapeTaskSerializer

    def get_serializer_class(self):
        if self.request.version == 'v1':
            return ShoalScrapeTaskSerializer
        return EmbeddedShoalScrapeTaskSerializer

    def update(self, request, *args, **kwargs):
        new_state = request.data.get('state', None)
        commit = request.data.get('commit', False)

        if new_state is not None:
            instance = self.get_object()

            if new_state not in ShoalScrapeTask.ALL_STATES:
                raise DRFValidationError({'state': 'State must be one of these'
                                          ' values: {}'
                                          ''.format(ShoalScrapeTask.ALL_STATES)})
            elif commit:
                instance.set_state(int(new_state))

            serializer = self.get_serializer(instance)
            return Response(serializer.data)

        return super(ShoalScrapeTaskViewSet, self).update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        shoalscrape_task_id = kwargs.get('pk')
        try:
            if ShoalScrapeTask.objects.get(id=shoalscrape_task_id).state == 1:
                return Response({'non_field_errors': 'ShoalScrapeTask {} is in'
                                 ' progress and may not be deleted.'
                                 ''.format(shoalscrape_task_id)},
                                status=status.HTTP_409_CONFLICT)
        except ShoalScrapeTask.DoesNotExist:
            pass
        return super(ShoalScrapeTaskViewSet, self).destroy(request, *args, **kwargs)

    @list_route()
    def choices(self, request, *args, **kwargs):
        return Response({'state': ShoalScrapeTask.STATE_CHOICES})


class CustomJSONWebTokenAPIView(JSONWebTokenAPIView):
    serializer_class = JSONWebTokenSerializer

    def post(self, *args, **kwargs):
        response = super(CustomJSONWebTokenAPIView, self).post(*args, **kwargs)
        for each in response.data.get('non_field_errors', list()):
            if each == 'Unable to login with provided credentials.':
                response.status_code = 401
                response.reason_phrase = "UNAUTHORIZED"
        return response


# Reference: http://jsatt.com/blog
#                    /abusing-django-rest-framework-part-1-non-model-endpoints/
class PreviewLandingPage(APIView):
    http_method_names = ('get', 'options')

    def get(self, request, *args, **kwargs):
        landing_page_id = kwargs.get('landing_page_id')
        engagement_id = kwargs.get('engagement_id', None)
        target_id = kwargs.get('target_id', None)
        page_source = None

        try:
            landing_page = LandingPage.objects.get(id=landing_page_id)
            if landing_page.status == 2:
                return Response({'non_field_errors': 'Landing page with ID {}'
                                 ' is still being generated'
                                 ''.format(landing_page_id)})

            with open(landing_page.path, 'r') as file:
                page_source = file.read()

            if engagement_id is not None:
                target = Target.objects.get(id=target_id)
                engagement = Engagement.objects.get(id=engagement_id)
                page_source = replace_shortcodes(page_source, engagement,
                                                 target)
        except LandingPage.DoesNotExist:
            return Response({'non_field_errors': 'Landing page with ID {} not'
                             ' found'.format(landing_page_id)},
                            status=status.HTTP_404_NOT_FOUND)
        except Target.DoesNotExist:
            return Response({'non_field_errors': 'Target with ID {} not'
                             ' found'.format(target_id)},
                            status=status.HTTP_404_NOT_FOUND)
        except Engagement.DoesNotExist:
            return Response({'non_field_errors': 'Engagement with ID {} not'
                             ' found'.format(engagement_id)},
                            status=status.HTTP_404_NOT_FOUND)
        except IOError:
            return Response({'non_field_errors': 'Landing page has defunct'
                             ' path: {}'.format(landing_page.path)},
                            status=status.HTTP_404_NOT_FOUND)
        except TypeError:
            return Response({'non_field_errors': 'Landing page with ID {} is'
                             ' still being generated'.format(landing_page_id)})

        # Remove all target attributes (they open new tabs from anchor links):
        page_source = re.sub(r'target=".*?"', '', page_source, flags=re.DOTALL)

        # Swap all anchor href values with "#", leaving other attributes alone:
        regex = re.compile(r'(<a.*?href=)(".*?")', flags=re.DOTALL)
        page_source = regex.sub(r'\1"#"', page_source)

        response = Response({'source': page_source})

        return response


class CheckEmailTemplateShortcodes(APIView):
    http_method_names = ('post', 'options')

    def post(self, request, *args, **kwargs):
        template = request.data.get('template', None)
        target_list_id = request.data.get('target_list_id', None)

        if template is None:
            return Response({'template': 'This field is required.'},
                            status=status.HTTP_400_BAD_REQUEST)
        if target_list_id is None:
            return Response({'target_list_id': 'This field is required.'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            target_list = TargetList.objects.get(id=target_list_id)
        except TargetList.DoesNotExist:
            return Response({'target_list_id': 'Target list with ID {} does'
                             ' not exist.'.format(target_list_id)},
                            status=status.HTTP_400_BAD_REQUEST)

        targets = target_list.target.all()

        if not targets.exists():
            return Response({'target_list_id': 'Target list with ID {} has no'
                             ' targets.'.format(target_list_id)},
                            status=status.HTTP_400_BAD_REQUEST)

        target_data_labels = TargetDatum.objects.filter(target__in=targets).\
                                                 distinct('label').\
                                                 values_list('label')
        target_data_labels = list([k[0] for k in target_data_labels])
        target_data_labels.extend(['url', 'firstname', 'lastname', 'email',
                                   'timezone'])
        shortcode_errors = []
        for index, each_line in enumerate(template.split('\n'), 1):
            found_shortcodes = re.findall(r'.*?\[\#\[(.*?)\]\#\].*?',
                                          each_line,
                                          flags=re.DOTALL)
            for each_shortcode in found_shortcodes:
                if each_shortcode not in target_data_labels:
                    shortcode_errors.append((each_shortcode, index))
        return Response({'shortcode_errors': shortcode_errors})


class PreviewVectorEmailView(APIView):
    http_method_names = ('get', 'options')

    def get(self, request, *args, **kwargs):
        vector_email_id = kwargs.get('vector_email_id')
        try:
            vector_email = VectorEmail.objects.get(id=vector_email_id)
        except VectorEmail.DoesNotExist:
            return Response({'non_field_errors': 'Vector email not found'},
                            status=status.HTTP_400_BAD_REQUEST)

        if vector_email.custom_email_template is True and \
                vector_email.email_template is None:
            return Response({'non_field_errors': 'Vector email has no'
                             ' email_template'},
                            status=status.HTTP_400_BAD_REQUEST)
        elif vector_email.engagement.email_template is None:
            return Response({'non_field_errors': 'Vector email\'s engagement'
                             ' (#{}) has no email_template'
                             ''.format(vector_email.engagement.id)},
                            status=status.HTTP_400_BAD_REQUEST)

        data = generateContent(vector_email.target, vector_email.engagement)

        subject, text, html, from_email, recipient, from_address = data

        # The next line breaks "Open," "Click," and "Submit" events.
        html = html.replace(vector_email.engagement.url, 'broken-for-preview')

        # Remove all `target` attributes. These open new tabs for anchor links.
        html = re.sub(r'target=".*?"', '', html, flags=re.DOTALL)

        # Swap all anchor href links with `#`, leaving other attributes alone.
        regex = re.compile(r'(<a.*?href=)(".*?")', flags=re.DOTALL)
        html = regex.sub(r'\1"#"', html)

        return Response({'source': html})


class CSVUploadView(APIView):
    parser_classes = (MultiPartParser, FormParser)
    http_method_names = ('post', 'options')

    def post(self, request, *args, **kwargs):
        filename = request.FILES['file'].name
        file_object = request.FILES['file']

        target_list = create_target_list_from_csv(file_object, filename)

        return Response({'target_list': target_list})


class CheckEmailSettingsView(APIView):
    http_method_names = ('post', 'options')

    def post(self, request, *args, **kwargs):
        for field in ('host', 'port', 'login', 'password', 'use_tls',
                      'test_recipient'):
            if request.data.get(field, None) is None:
                return Response({field: 'This field is required.'},
                                status=status.HTTP_400_BAD_REQUEST)

        host = request.data.get('host')
        port = request.data.get('port')
        login = request.data.get('login')
        password = request.data.get('password')
        use_tls = request.data.get('use_tls')
        test_recipient = request.data.get('test_recipient')

        email_backend = EmailBackend(host=host, port=int(port),
                                     username=login, password=password,
                                     use_tls=use_tls)

        body = 'If you received this email, email settings are correct.'
        try:
            EmailMessage('Test email', body, login, [test_recipient],
                         connection=email_backend).send()
            return Response({'success': True, 'error_message': None})
        except Exception as e:
            return Response({'success': False, 'error_message': str(e)})


class TargetListFlatViewSet(VersionableDynamicModelViewSet):
    model = TargetList
    queryset = TargetList.objects.all()
    serializer_class = TargetListFlatSerializer
    http_method_names = ('get', 'post', 'patch', 'options')

    def get_serializer_class(self):
        if self.request.version == 'v1':
            return TargetListFlatSerializer
        return EmbeddedTargetListFlatSerializer

    def create(self, request, *args, **kwargs):
        with transaction.atomic():
            # "target_list" request format:
            if 'target_list' in request.data.keys():
                target_list_data = request.data.get('target_list')
            # "target_lists" request format:
            elif 'target_lists' in request.data.keys():
                target_lists = request.data.get('target_lists')
                assert type(target_lists) == list
                if len(target_lists) > 1:
                    raise DRFValidationError(
                        {'target_lists': 'target-lists-flat-view does not'
                         ' support deserialization of more than one target'
                         ' list at a time'}
                    )
                target_list_data = target_lists[0]
            # Bare-object request format:
            else:
                target_list_data = request.data

            nickname = target_list_data.get('nickname', None)
            description = target_list_data.get('description')
            client_id = target_list_data.get('client', None)
            unprocessed_targets = target_list_data.get('target', None)

            # Use falsiness to catch empty strings for nickname.
            if not nickname:
                raise DRFValidationError({'nickname': 'This field may not be blank.'})
            if client_id is None:
                raise DRFValidationError({'client': 'This field is required.'})

            try:
                client = Client.objects.get(id=client_id)
            except Client.DoesNotExist:
                raise DRFValidationError({'client': 'Client not found.'})
            except TypeError:
                raise DRFValidationError({'client': 'Not a valid Client ID.'})

            target_list = TargetList(nickname=nickname,
                                     client=client,
                                     description=description)
            target_list.save()

            if unprocessed_targets is not None:
                for mixed_data in unprocessed_targets:
                    target, mixed_data = retrieve_target_from_mixed_data(mixed_data)
                    target.save()
                    target_list.target.add(target)

                    # Wrapped in atomic, this check might fail; that would mean
                    # the item id not yet exist, and would have no TargetData.
                    if target.id:
                        current_data = TargetDatum.objects.filter(target_list=target_list,
                                                                  target=target)
                    else:
                        current_data = list()

                    new_labels = mixed_data.keys()

                    for extant_datum in current_data:
                        if extant_datum.label in new_labels:
                            extant_datum.value = mixed_data[extant_datum.label]
                            extant_datum.save()
                            mixed_data.pop(extant_datum.label)
                        else:
                            extant_datum.delete()

                    for new_label in new_labels:
                        new_datum = TargetDatum(target_list=target_list,
                                                target=target,
                                                label=new_label,
                                                value=mixed_data[new_label])
                        new_datum.save()

        serializer_class = self.get_serializer_class()
        serializer_instance = serializer_class(target_list)
        return Response({'target_list': serializer_instance.data})

    def update(self, request, *args, **kwargs):
        with transaction.atomic():
            target_list = self.get_object()

            # "target_list" request format:
            if 'target_list' in request.data.keys():
                target_list_data = request.data.get('target_list')
            # "target_lists" request format:
            elif 'target_lists' in request.data.keys():
                target_lists = request.data.get('target_lists')
                assert type(target_lists) == list
                if len(target_lists) > 1:
                    raise DRFValidationError(
                        {'target_lists': 'target-lists-flat-view does not'
                         ' support deserialization of more than one target'
                         ' list at a time'}
                    )
                target_list_data = target_lists[0]
            # Bare-object request format:
            else:
                target_list_data = request.data

            target_list.nickname = target_list_data.get('nickname',
                                                        target_list.nickname)
            target_list.description = target_list_data.get('description',
                                                           target_list.description)
            client_id = target_list_data.get('client', target_list.client.id)
            unprocessed_targets = target_list_data.get('target', None)

            # Use falsiness to catch empty strings for nickname.
            if not target_list.nickname:
                raise DRFValidationError({'nickname': 'This field may not be blank.'})
            if client_id is None:
                raise DRFValidationError({'client': 'This field is required.'})

            try:
                target_list.client = Client.objects.get(id=client_id)
            except Client.DoesNotExist:
                raise DRFValidationError({'client': 'Client not found.'})
            except TypeError:
                raise DRFValidationError({'client': 'Not a valid Client ID.'})

            target_list.save()

            if unprocessed_targets is not None:
                target_list.target.clear()
                for mixed_data in unprocessed_targets:
                    target, mixed_data = retrieve_target_from_mixed_data(mixed_data)
                    target.save()
                    target_list.target.add(target)

                    # Wrapped in atomic, this check might fail; that would mean
                    # the item id not yet exist, and would have no TargetData.
                    if target.id:
                        current_data = TargetDatum.objects.filter(target_list=target_list,
                                                                  target=target)
                    else:
                        current_data = list()

                    new_labels = mixed_data.keys()
                    for extant_datum in current_data:
                        if extant_datum.label in new_labels:
                            extant_datum.value = mixed_data[extant_datum.label]
                            extant_datum.save()
                            mixed_data.pop(extant_datum.label)
                        else:
                            extant_datum.delete()

                    for new_label in mixed_data.keys():
                        new_datum = TargetDatum(target_list=target_list,
                                                target=target,
                                                label=new_label,
                                                value=mixed_data[new_label])
                        new_datum.save()

        serializer_class = self.get_serializer_class()
        serializer_instance = serializer_class(target_list)
        return Response({'target_list': serializer_instance.data})


class EmailLogViewSet(VersionableDynamicModelViewSet):
    model = VectorEmail
    queryset = VectorEmail.objects.all()
    serializer_class = EmbeddedEmailLogSerializer
    http_method_names = ('get', 'options')

    def get_serializer_class(self):
        if self.request.version == 'v1':
            return EmailLogSerializer
        return EmbeddedEmailLogSerializer


class CheckPhishingDomainView(APIView):
    http_method_names = ('post', 'options')

    def post(self, request, *args, **kwargs):
        protocol = request.data.get('protocol', None)
        domain_name = request.data.get('domain_name', None)
        ip = None

        try:
            sb_ip = SiteSettings.load().public_ip
        except (SiteSettings.DoesNotExist, AttributeError):
            sb_ip = None
        # Also covers the case where the public_ip setting is null.
        if sb_ip is None:
            sb_ip = '127.0.0.1'

        if protocol is None:
            return Response({'protocol': 'This field is required.'},
                            status=status.HTTP_400_BAD_REQUEST)
        if domain_name is None:
            return Response({'domain_name': 'This field is required.'},
                            status=status.HTTP_400_BAD_REQUEST)

        if domain_name.startswith(('https://', 'http://')):
            return Response({'domain_name': 'The domain name to check may not'
                                            ' start with a protocol.'},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            ping_request = urllib2.Request('{}://{}'.format(protocol,
                                                            domain_name))
            response = urllib2.urlopen(ping_request,
                                       timeout=settings.PING_TIMEOUT)
            ip = gethostbyname(urlparse(response.geturl()).hostname)
        except urllib2.HTTPError as e1:
            ip = gethostbyname(urlparse(e1.geturl()).hostname)
        except urllib2.URLError as e1:
            try:
                # Sometimes SSL certs can break urlopen with a URLError.
                # Even using this, TLSv1 was causing "URLError: <urlopen error
                # EOF occurred in violation of protocol (_ssl.c:590)>", so this
                # might need tweaking if TLSv1_2 should ever start to fail.
                fake_ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
                response = urllib2.urlopen(ping_request,
                                           timeout=settings.PING_TIMEOUT,
                                           context=fake_ssl_context)
                ip = gethostbyname(urlparse(response.geturl()).hostname)
            except urllib2.HTTPError as e2:
                ip = gethostbyname(urlparse(e2.geturl()).hostname)
            except Exception as e2:
                # If it's not an SSL problem, report the original error.
                error_message = 'Domain name not found: {}'.format(str(e1))
                logger.info('[ ! ] check_domain failure:'
                            '\n    ip: {}\n    sb_ib: {}'
                            '\n    e1: {}\n    e2: {}'.format(ip, sb_ip,
                                                              str(e1), str(e2)))
                return Response({'success': False,
                                 'error_message': error_message})

        if ip == sb_ip:
            error_message = ('Server exists at {} and matches Sandbar host'
                             ' IP at {}'.format(ip, sb_ip))
            logger.info('[ + ] check_domain success:\n    {}'
                        ''.format(error_message))
            return Response({'success': True,
                             'error_message': error_message})
        else:
            error_message = ('Server exists at {} and does not match'
                             ' Sandbar host IP at {}'.format(ip, sb_ip))
            logger.info('[ - ] check_domain success:\n    {}'
                        ''.format(error_message))
            return Response({'success': False,
                             'error_message': error_message})


class OAuthConsoleViewSet(VersionableDynamicModelViewSet):
    model = OAuthResult
    queryset = OAuthResult.objects.all()
    serializer_class = EmbeddedOAuthConsoleSerializer
    http_method_names = ('get', 'options')

    def get_serializer_class(self):
        if self.request.version == 'v1':
            return OAuthConsoleSerializer
        return EmbeddedOAuthConsoleSerializer


class GmailMessagesView(APIView):
    http_method_names = ('post', 'options')

    def post(self, request, *args, **kwargs):
        """
        Optional request data:
            str pageToken
                -- Should be a length 20 hex value.
                -- If no pageToken is supplied, the request will retrieve the
                    first message(s) matching the rest of the parameters.
                -- Default: ""
            str format
                -- Choices: ["minimal", "metadata", "full", "raw"]
                -- Default: "minimal"
            str maxResults
                -- An integer may also be used.
                -- Default: 10
            bool includeSpamTrash
                -- Indicates whether or not to include messages the user marked
                    as spam or trashed.
                -- Default: true
            str searchQuery
                -- Should obey these rules:
                    https://support.google.com/mail/answer/7190
                -- If no searchQuery is supplied, no search query will be used.
                -- Default: ""
        """
        # Request data for Sandbar
        oauth_result = OAuthResult.objects.get(id=kwargs.get('oa_result_id'))

        # Request data for Gmail
        page_token = request.data.get('pageToken', '')
        requested_format = request.data.get('format', 'minimal')
        search_query = request.data.get('searchQuery', '')
        max_results = request.data.get('maxResults', '10')
        include_spam_trash = request.data.get('includeSpamTrash', True)

        # Request data validation
        if page_token and len(page_token) != 20:
            return Response({'pageToken': 'pageToken should be 20 characters'
                                          ' or empty'},
                            status=status.HTTP_400_BAD_REQUEST)

        # Constructing the list request
        list_params = {'maxResults': max_results,
                       'includeSpamTrash': include_spam_trash,
                       'pageToken': page_token,
                       'fields': 'messages,nextPageToken,resultSizeEstimate'}
        if search_query:
            list_params.update({'q': search_query})

        # Performing the list request
        list_response = google_api.messages_list(oauth_result,
                                                 params=list_params)

        # Parsing and validating the list response data
        next_page_token = list_response.get('nextPageToken', '')
        messages = list_response.get('messages', None)
        if messages is None:
            return Response({'service_error': '\'messages\' missing'},
                            status=status.HTTP_502_BAD_GATEWAY)

        # Constructing the batched get requests
        get_params = {'format': requested_format}
        message_ids = [each['id'] for each in messages]

        # Performing the batched get requests
        message_batch = google_api.batched_messages_get(oauth_result,
                                                        message_ids,
                                                        params=get_params)

        # Parsing the batched get requests
        for each_message in message_batch:
            if requested_format in ('metadata', 'full', 'raw'):
                if 'payload' not in each_message.keys():
                    each_message['payload'] = dict()

            if requested_format in ('metadata', 'full'):
                each_message = process_gmail_message_headers(each_message)

            if requested_format in ('full', 'raw'):
                each_message = process_gmail_message_body(each_message,
                                                          requested_format)

        return Response({'messages': message_batch,
                         'nextPageToken': next_page_token})


class PhishingResultViewSet(VersionableDynamicModelViewSet):
    model = ResultEvent
    queryset = ResultEvent.objects.all()
    serializer_class = EmbeddedPhishingResultSerializer
    http_method_names = ('get', 'options')

    def get_serializer_class(self):
        if self.request.version == 'v1':
            return PhishingResultSerializer
        return EmbeddedPhishingResultSerializer


class DriveFilesView(APIView):
    http_method_names = ('post', 'options')

    def post(self, request, *args, **kwargs):
        """
        Optional request data:
            str pageToken
                -- If no pageToken is supplied, the request will retrieve the
                    first file(s) for the request's search query.
                -- Default: ""
            str fields
                -- Can use fields and field syntax from the fields editor here:
                    https://developers.google.com/apis-explorer/#p/drive/v3/drive.files.list
                -- These fields will always be included:
                    ["parents", "id", "name", "kind", "mimeType"]
                -- Default: ""
            str pageSize
                -- An integer may also be used.
                -- Default: 10
            bool includeDirectories
                -- When false, adds this string to the search query:
                    "mimeType != 'application/vnd.google-apps.folder'"
                -- Default: true
            bool includeFiles
                -- When false, adds this string to the search query:
                    "mimeType = 'application/vnd.google-apps.folder'"
                -- Default: true
            str directoryId
                -- If supplied, adds this string to the search query:
                    "'directoryId' in parents"
                -- Default: ""
            str searchQuery
                -- If supplied, the searchQuery string will be concatenated
                    with all other search query modifications added by request
                    parameters. (includeDirectories, includeFiles, directoryId)
                -- Reference:
                    https://developers.google.com/drive/v3/web/search-parameters
                -- Default: ""
        """
        oa_result = OAuthResult.objects.get(id=kwargs.get('oa_result_id'))

        # "kind" is not sufficient to distinguish between files and folders;
        # "mimeType" is necessary.
        default_fields = ['parents', 'id', 'name', 'kind', 'mimeType']
        params = dict()
        q_string = list()

        page_token = request.data.get('pageToken', '')
        page_size = request.data.get('pageSize', '10')
        fields = request.data.get('fields', list())

        # Permit null as a default for empty or malformed request booleans.
        include_dirs = request.data.get('includeDirectories', True)
        include_files = request.data.get('includeFiles', True)

        directory_id = request.data.get('directoryId', '')
        search_query = request.data.get('searchQuery', '')

        if page_token:
            params.update({'pageToken': page_token})

        if (include_dirs is False) and (include_files is False):
            error = 'includeDirectories and includeFiles may not both be false'
            raise DRFValidationError({'includeDirectories': error,
                                      'includeFiles': error})

        if type(fields) != list:
            raise DRFValidationError({'fields': 'Must be a list'})

        fields.extend(default_fields)

        # Constructing the search query
        if include_dirs is False:
            q_string.append("mimeType != 'application/vnd.google-apps.folder'")

        if include_files is False:
            q_string.append("mimeType = 'application/vnd.google-apps.folder'")

        if directory_id:
            q_string.append('\'{}\' in parents'.format(directory_id))

        if search_query:
            q_string.append(search_query)

        joined_fields = 'nextPageToken, files({})'.format(','.join(fields))
        joined_search_query = ' and '.join(q_string)

        params.update({'pageSize': page_size,
                       'fields': joined_fields,
                       'q': joined_search_query})

        try:
            data = google_api.files_list(oa_result, params=params)
            return Response(data)
        except Exception as e:
            try:
                # Google's errors benefit from unpacking.
                error = str(json.loads(e.content)['error'])
                return Response({'service_error': error},
                                status=status.HTTP_502_BAD_GATEWAY)
            except:
                # If it doesn't have Google's structure, it's not from them.
                raise e
