# -*- coding: utf-8 -*-
from googleapiclient.http import MediaIoBaseDownload
from random import getrandbits
from urlparse import urlparse
from socket import gethostbyname
from tempfile import mkstemp, TemporaryFile
from wsgiref.util import FileWrapper
from io import open as io_open
from io import BytesIO
import zipfile
import urllib2
import ssl
import datetime
import json
import base64
import logging
import os
import re
import csv

from django.contrib import messages as django_messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import FieldDoesNotExist
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.http.response import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from django.core.mail import EmailMessage
from django.core.mail.backends.smtp import EmailBackend
from django.utils import timezone as dj_tz

from client.data_management import zip_data_for_export, load_data_from_zip_file
from client.forms import *
from client.models import *
from client.tasks import generateContent
from client.helpers import replace_shortcodes, split_and_clean_url
from client import google_api
from api.serializers import *
from page_parser.tasks import parse_page
from sandbar import settings

logger = logging.getLogger(__name__)


@login_required
def engagement_preview_data(request, engagement_id):
    engagement_preview_data = {}
    engagement = Engagement.objects.get(id=engagement_id)
    target_list_names = [t.nickname for t in engagement.target_lists.all()]
    vector_emails = VectorEmail.objects.filter(engagement=engagement)
    first_ve = vector_emails.first()
    engagement_preview_data.\
        update({'engagement_id': engagement.id,
                'engagement_name': engagement.name,
                'is_oauth': engagement.is_oauth,
                'target_list_names': ', '.join(target_list_names),
                'total_target_count': vector_emails.count()})

    try:
        missing_shortcodes = list(check_engagement_email_shortcodes(engagement))
        engagement_preview_data.\
            update({'missing_shortcodes': missing_shortcodes})
    except AttributeError:
        engagement_preview_data.\
            update({'missing_shortcodes': ['EMAIL TEMPLATE NOT FOUND']})

    try:
        target = first_ve.target
        datatuple = generateContent(target, engagement)
        subject, text, html, from_email, recipient, from_address = datatuple
        first_ve_target_list = first_ve.target.targetlist_set.filter(engagement=engagement).last().nickname
        server_tz = dj_tz.get_default_timezone()
        naive_send_at = dj_tz.make_naive(first_ve.send_at)
        localized = server_tz.localize(naive_send_at)
        readable = localized.strftime('%B %d, %Y, %I:%M %p')
        formatted_send_at = ('{} ({})'.format(readable, server_tz))
        engagement_preview_data.\
            update({'from_email': from_email,
                    'subject': subject,
                    'first_ve_target_id': first_ve.target.id,
                    'first_ve_target_email': first_ve.target.email,
                    'first_ve_target_list': first_ve_target_list,
                    'first_ve_send_at': formatted_send_at})
    except AttributeError:
        engagement_preview_data.\
            update({'from_email': "TARGET NOT FOUND",
                    'subject': "TARGET NOT FOUND",
                    'first_ve_target_id': -1,
                    'first_ve_target_email': "TARGET NOT FOUND",
                    'first_ve_target_list': "TARGET NOT FOUND",
                    'first_ve_send_at': "TARGET NOT FOUND"})

    try:
        # Support for VectorEmail-specific landing and redirect pages.
        if first_ve.custom_landing_page:
            vemail_landing_page = first_ve.landing_page
        else:
            vemail_landing_page = engagement.landing_page
        engagement_preview_data.update({
            'first_ve_landing_page_id': vemail_landing_page.id,
            'first_ve_landing_page_name': vemail_landing_page.name,
            'first_ve_landing_page_url': vemail_landing_page.url,
            'first_ve_landing_page_type': vemail_landing_page.\
                                          get_page_type_display()
        })
    except AttributeError:
        engagement_preview_data.update({
            'first_ve_landing_page_id': -1,
            'first_ve_landing_page_name': "LANDING PAGE NOT FOUND",
            'first_ve_landing_page_url': "LANDING PAGE NOT FOUND",
            'first_ve_landing_page_type': "LANDING PAGE NOT FOUND"
        })

    try:
        if first_ve.custom_redirect_page:
            vemail_redirect_page = first_ve.redirect_page
        else:
            vemail_redirect_page = engagement.redirect_page
        engagement_preview_data.update({
            'first_ve_redirect_page_id': vemail_redirect_page.id,
            'first_ve_redirect_page_name': vemail_redirect_page.name,
            'first_ve_redirect_page_url': vemail_redirect_page.url,
            'first_ve_redirect_page_type': vemail_redirect_page.\
                                          get_page_type_display()
        })
    except AttributeError:
        engagement_preview_data.update({
            'first_ve_redirect_page_id': -1,
            'first_ve_redirect_page_name': "REDIRECT PAGE NOT FOUND",
            'first_ve_redirect_page_url': "REDIRECT PAGE NOT FOUND",
            'first_ve_redirect_page_type': "REDIRECT PAGE NOT FOUND"
        })

    try:
        engagement_preview_data.\
            update({'engagement_schedule_name': engagement.schedule.name})
    except AttributeError:
        engagement_preview_data.\
            update({'engagement_schedule_name': "SCHEDULE NOT FOUND"})

    # Prevent string/int field None values from becoming "undefined" in JS:
    for key, value in engagement_preview_data.iteritems():
        if value is None:
            engagement_preview_data[key] = -1

    return JsonResponse(engagement_preview_data)


@login_required
def preview_engagement_email_template(request, engagement_id, target_id):
    context = {'soup': None}
    engagement = Engagement.objects.get(id=engagement_id)
    target = Target.objects.get(id=target_id)
    vector_email = VectorEmail.objects.get(engagement=engagement,
                                           target=target)
    if vector_email:
        datatuple = generateContent(target, engagement)
        subject, text, html, from_email, recipient, from_address = datatuple

        if engagement.is_oauth:
            # Breaking tracking images for OAuthEngagements requires ignoring
            # the referral ID in the URL, which requires knowing what the first
            # part of the URL (ie, the callback's domain name) is.
            url = engagement.oauth_consumer.callback_url

            segmented_url = split_and_clean_url(url)

            if segmented_url[0] == 'https:' or segmented_url[0] == 'http:':
                segmented_url.pop(0)

            domain = segmented_url[0]

            link_to_break = domain

        # For other types of engagements, only the domain_name should be
        # replaced, since the Engagement's URL will have a referral ID embedded
        # in its path as a segment which would need to be removed.
        else:
            link_to_break = engagement.domain.domain_name

        # The next line breaks "Open," "Click," and "Submit" events.
        html = html.replace(link_to_break, 'broken-for-preview')

        # Remove all `target` attributes. These open new tabs for anchor links.
        html = re.sub(r'target=".*?"', '', html, flags=re.DOTALL)

        # Swap all anchor href links with `#`, leaving other attributes alone.
        regex = re.compile(r'(<a.*?href=)(".*?")', flags=re.DOTALL)
        html = regex.sub(r'\1"#"', html)

        context.update({'soup': html})
    else:
        error_template = ('preview_engagement_email_template error: '
                          'VectorEmails not found for Engagement '
                          '{}'.format(request.POST.get('engagement_id', None)))
        logger.info(error_template)
        context.update({'soup': '<h1>{}<h1>'.format(str(error_template))})

    response = render(request, 'index.html', context)
    return response


@login_required
def preview_page(request, landing_page_id, engagement_id=None, target_id=None):
    page_source = None
    engagement = None
    target = None
    if landing_page_id:
        try:
            landingPage = LandingPage.objects.get(id=landing_page_id)
            if landingPage.status == 2:
                return render(request, 'in_process.html', {})

            try:
                engagement = Engagement.objects.get(id=engagement_id)
            except Engagement.DoesNotExist:
                pass
            try:
                target = Target.objects.get(id=target_id)
            except Target.DoesNotExist:
                pass

            with io_open(landingPage.path, 'r', encoding='utf-8') as f:
                page_source = f.read()
                if engagement:
                    page_source = replace_shortcodes(page_source, engagement,
                                                     target)
        except LandingPage.DoesNotExist:
            raise Http404
        except IOError:
            raise Http404
        except TypeError:
            raise Http404('This page is still being generated')

    if page_source is None:
        # This could use a more specific error message for the user.
        response = render(request, 'external_404.html', status=404)
    else:
        # Remove all `target` attributes. These open new tabs for anchor links.
        page_source = re.sub(r'target=".*?"', '', page_source, flags=re.DOTALL)

        # Swap all anchor href links with `#`, leaving other attributes alone.
        regex = re.compile(r'(<a.*?href=)(".*?")', flags=re.DOTALL)
        page_source = regex.sub(r'\1"#"', page_source)

        response = render(request, 'index.html', {'soup': page_source})
    if engagement:
        response.set_cookie('engagement_id', engagement.id)

    return response


@login_required
def serve_plunder(request, plunder_id):
    plunder = None
    try:
        plunder = Plunder.objects.get(id=plunder_id)

        with open(plunder.path, 'rb') as plunder_file:
            wrapper = FileWrapper(plunder_file)
            response = HttpResponse(wrapper, content_type=plunder.mimetype)
            sanitized_filename = os.path.split(plunder.filename)[1]
            disposition = 'attachment; filename={}'.format(sanitized_filename)
            response['Content-Disposition'] = disposition
            return response

    except Exception as e:
        error = '[ ! ] Error while attempting download: {}'.format(e)
        logger.info(error)
        django_messages.warning(request, error)
        return JsonResponse({'error': error}, safe=False)


def add_default_ordering(sorting, default):
    if sorting is None:
        return default
    sorting = sorting.split(',')
    if default and (default.strip('-') not in sorting and
                    '-%s' % default.strip('-') not in sorting):
        sorting.append(default)
    return ','.join(sorting)


def __ordering(request, cls, default='', _filter=None):
    sorting = request.GET.get('order_by')
    pg_size = request.GET.get('pg_size', 25)
    sorting_list = []
    sorting = add_default_ordering(sorting, default)
    if sorting:
        for sort in sorting.split(','):
            try:
                cls._meta.get_field(sort.lstrip('-'))
                sorting_list.append(sort)
            except FieldDoesNotExist:
                pass
    objects = cls.objects.all().\
        order_by(*sorting_list)
    if _filter:
        objects = objects.filter(**_filter)
    page = request.GET.get('page', 1)
    paginator = Paginator(objects, pg_size)
    page = paginator.page(page)

    return page


@login_required
def campaignsList(request):
    _filter = ''
    if request.GET.get('client'):
        _filter = {'client': request.GET['client']}
    page = __ordering(request, Campaign, default='-id', _filter=_filter)

    return render(request, 'campaigns_list.html',
                  {'page': page, 'apage': 'campaigns',
                   'objects': page.object_list,
                   'sorting': request.GET.get('order_by'),
                   'clients': Client.objects.order_by('-id'),
                   'client': request.GET.get('client', 0)})


@login_required
def campaignEdit(request, id=None):
    client = None
    campaign = None
    page = None
    engagements = []
    vector_emails = []

    sorting = request.GET.get('order_by', '')
    pg_size = request.GET.get('pg_size', 25)
    f_status = request.GET.get('filter_status')
    _filter = {'state__gt': -1}
    if f_status:
        _filter.pop('state__gt')
        _filter['state'] = f_status

    if request.method == 'GET':
        try:
            campaign = Campaign.objects.get(id=id)
            engagements = Engagement.objects.filter(campaign=campaign)
            client = campaign.client
            initial = {'name': campaign.name,
                       'description': campaign.description,
                       'client': client,
                       'campaign_id': campaign.id}
            form = CampaignForm(initial=initial)
        except Campaign.DoesNotExist:
            form = CampaignForm()
    else:
        form = CampaignForm(request.POST)
        if form.is_valid():
            client = form.cleaned_data['client']
            name = form.cleaned_data['name']
            description = form.cleaned_data.get('description')
            try:
                campaign = Campaign.objects.get(id=id)
                campaign.name = name
                campaign.client = client
                campaign.description = description
                campaign.save()
            except Campaign.DoesNotExist:
                Campaign.objects.create(client=client,
                                        name=name,
                                        description=description)

            return redirect('/campaigns/list/')
        else:
            return JsonResponse(form.errors.as_json(), safe=False)

    if campaign:
        _filter['engagement__campaign'] = campaign.id
        form.fields['client'].widget.attrs['readonly'] = 'readonly'
        form.fields['client'].widget.attrs['disabled'] = 'disabled'
        vector_emails = VectorEmail.objects.filter(engagement=Engagement.objects.
                                                   filter(campaign=campaign))

    filter_status = [(k, v) for k, v in VectorEmail.STATE_CHOICES if k > 0]
    context = {'form': form,
               'apage': 'campaigns',
               'page': page,
               'campaign': campaign,
               'engagements': engagements,
               'client': client,
               'vector_emails': vector_emails,
               'sorting': sorting,
               'pg_size': pg_size,
               'filter_status': filter_status,
               'fs': f_status}

    if vector_emails:
        extra_columns = ['engagement__id', 'engagement__name']
        vector_email_list_context = prepare_vector_email_list(request,
                                                              extra_columns,
                                                              _filter)
        context.update(vector_email_list_context)

    return render(request, 'campaign_edit.html', context)


@login_required
def engagementsList(request):
    _filter = ''
    if request.GET.get('client'):
        _filter = {'campaign__client': request.GET['client']}
    page = __ordering(request, Engagement, default='-id', _filter=_filter)

    return render(request, 'engagements_list.html',
                  {'page': page, 'apage': 'engagements',
                   'objects': page.object_list,
                   'sorting': request.GET.get('order_by'),
                   'clients': Client.objects.order_by('-id'),
                   'client': request.GET.get('client', 0)})


@login_required
def engagementEdit(request, id=None, is_oauth=False):
    if is_oauth:
        model_class = OAuthEngagement
        form_class = OAuthEngagementForm
    else:
        model_class = Engagement
        form_class = EngagementForm
    engagement = None
    page = None
    vector_emails = []

    sorting = request.GET.get('order_by', '')
    pg_size = request.GET.get('pg_size', 25)
    f_status = request.GET.get('filter_status')
    _filter = {'state__gt': -1}
    if f_status:
        _filter.pop('state__gt')
        _filter['state'] = f_status

    if request.method == 'GET':
        try:
            engagement = model_class.objects.get(id=id)
            initial = {'engagement_id': engagement.id,
                       'campaign': engagement.campaign,
                       'name': engagement.name,
                       'description': engagement.description,
                       'open_redirect': engagement.open_redirect,
                       'domain': engagement.domain,
                       'path': engagement.path,
                       'schedule': engagement.schedule,
                       'start_date': engagement.start_date,
                       'start_time': engagement.start_time,
                       'email_server': engagement.email_server,
                       'email_template': engagement.email_template,
                       'landing_page': engagement.landing_page,
                       'redirect_page': engagement.redirect_page,
                       'target_lists': engagement.target_lists.all()}
            if is_oauth:
                initial.update({'oauth_consumer': engagement.oauth_consumer})
            else:
                initial.update({'oauth_consumer': None})
            form = form_class(initial=initial)
        except model_class.DoesNotExist:
            form = form_class()
    else:
        form = form_class(request.POST)
        if form.is_valid():
            campaign = form.cleaned_data['campaign']
            name = form.cleaned_data['name']
            description = form.cleaned_data['description']
            open_redirect = form.cleaned_data.get('open_redirect')
            domain = form.cleaned_data.get('domain')
            path = form.cleaned_data.get('path')
            schedule = form.cleaned_data['schedule']
            start_date = form.cleaned_data['start_date']
            start_time = form.cleaned_data['start_time']
            email_server = form.cleaned_data['email_server']
            email_template = form.cleaned_data['email_template']
            landing_page = form.cleaned_data.get('landing_page', None)
            redirect_page = form.cleaned_data.get('redirect_page', None)
            target_lists = form.cleaned_data['target_lists']
            if is_oauth:
                oauth_consumer = form.cleaned_data['oauth_consumer']
            try:
                engagement = model_class.objects.get(id=id)
                engagement.campaign = campaign
                engagement.name = name
                engagement.description = description
                engagement.open_redirect = open_redirect
                engagement.domain = domain
                engagement.path = path
                engagement.schedule = schedule
                engagement.start_date = start_date
                engagement.start_time = start_time
                engagement.email_server = email_server
                engagement.email_template = email_template
                engagement.landing_page = landing_page
                engagement.redirect_page = redirect_page
                if is_oauth:
                    engagement.oauth_consumer = oauth_consumer
                engagement.save()

            except model_class.DoesNotExist:
                engagement = model_class(campaign=campaign,
                                         name=name,
                                         description=description,
                                         open_redirect=open_redirect,
                                         domain=domain,
                                         path=path,
                                         schedule=schedule,
                                         start_date=start_date,
                                         start_time=start_time,
                                         email_server=email_server,
                                         email_template=email_template,
                                         landing_page=landing_page,
                                         redirect_page=redirect_page)
                if is_oauth:
                    engagement.oauth_consumer = oauth_consumer
                engagement.save()
                engagement.target_lists.add(*target_lists)
                engagement.save()
                # New VectorEmails should only be created when their Engagement
                # is created.
                engagement.create_vector_emails()

            return JsonResponse({'engagement_id': engagement.id}, safe=False)
        else:
            return JsonResponse(form.errors.as_json(), safe=False)

    context = {}
    context.update({'open_redirects': OpenRedirect.objects.order_by('-id'),
                    'domains': PhishingDomain.objects.order_by('-id')})

    if engagement:
        _filter['engagement'] = engagement.id
        form.fields['target_lists'].widget.attrs['readonly'] = 'readonly'
        form.fields['target_lists'].widget.attrs['disabled'] = 'disabled'
        vector_emails = VectorEmail.objects.filter(engagement=engagement)
        if engagement.open_redirect:
            context.update({'open_redirect_id': engagement.open_redirect.id})
        if engagement.domain:
            context.update({'phishing_domain_id': engagement.domain.id})

    filter_status = [(k, v) for k, v in VectorEmail.STATE_CHOICES if k > 0]
    context.update({'form': form,
                    'apage': 'engagements',
                    'page': page,
                    'engagement': engagement,
                    'vector_emails': vector_emails,
                    'sorting': sorting,
                    'pg_size': pg_size,
                    'filter_status': filter_status,
                    'fs': f_status,
                    'is_oauth': is_oauth})

    if vector_emails:
        extra_columns = []
        vector_email_list_context = prepare_vector_email_list(request,
                                                              extra_columns,
                                                              _filter)
        context.update(vector_email_list_context)

    return render(request, 'engagement_edit.html', context)


@login_required
def usersList(request):
    page = __ordering(request, User, default='-id')

    return render(request, 'users_list.html',
                  {'page': page, 'apage': 'users',
                   'objects': page.object_list,
                   'sorting': request.GET.get('order_by')})


@login_required
def userEdit(request, id=None):
    user = None
    if request.method == 'GET':
        try:
            user = User.objects.get(id=id)
            initial = {'user_id': user.id,
                       'email': user.email,
                       'login': user.username,
                       'first_name': user.first_name,
                       'last_name': user.last_name}
            form = UserEditForm(initial=initial)
        except User.DoesNotExist:
            form = UserEditForm()
    else:
        form = UserEditForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['login']
            email = form.cleaned_data.get('email')
            first_name = form.cleaned_data.get('first_name')
            last_name = form.cleaned_data.get('last_name')
            password = form.cleaned_data.get('password')
            try:
                user = User.objects.get(id=id)
                if not password:
                    password = user.password
                else:
                    password = make_password(password)
                user.username = username
                user.email = email
                user.first_name = first_name
                user.last_name = last_name
                user.password = password
                user.is_staff = True
                user.is_active = True
                user.save()
            except User.DoesNotExist:
                User.objects.create(username=username,
                                    email=email,
                                    first_name=first_name,
                                    last_name=last_name,
                                    password=make_password(password)
                                    if password else None, is_staff=True,
                                    is_active=True)

            return redirect('/users/list/')
        else:
            return JsonResponse(form.errors.as_json(), safe=False)

    return render(request, 'user_edit.html',
                  {'form': form, 'user': user, 'apage': 'users', })


@login_required
def clientsList(request):
    page = __ordering(request, Client, default='-id')

    return render(request, 'clients_list.html',
                  {'page': page, 'apage': 'clients',
                   'objects': page.object_list,
                   'sorting': request.GET.get('order_by')})


@login_required
def clientEdit(request, id=None):
    client = None
    page = None
    campaigns = []
    targetLists = []
    vector_emails = []

    sorting = request.GET.get('order_by', '')
    pg_size = request.GET.get('pg_size', 25)
    f_status = request.GET.get('filter_status')
    _filter = {'state__gt': -1}
    if f_status:
        _filter.pop('state__gt')
        _filter['state'] = f_status

    if request.method == 'GET':
        try:
            client = Client.objects.get(id=id)
            targetLists = TargetList.objects.filter(client=client)
            campaigns = Campaign.objects.filter(client=client)
            initial = {'name': client.name,
                       'url': client.url,
                       'default_time_zone': client.default_time_zone,
                       'targetList': targetLists,
                       'campaigns': campaigns,
                       }
            form = ClientForm(initial=initial)
        except Client.DoesNotExist:
            form = ClientForm()
    else:
        form = ClientForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name']
            url = form.cleaned_data['url']
            default_time_zone = form.cleaned_data['default_time_zone']
            try:
                client = Client.objects.get(id=id)
                client.name = name
                client.url = url
                client.default_time_zone = default_time_zone
                client.save()
            except Client.DoesNotExist:
                Client.objects.create(name=name,
                                      url=url,
                                      default_time_zone=default_time_zone)

            return redirect('/clients/list/')
        else:
            return JsonResponse(form.errors.as_json(), safe=False)

    if campaigns:
        vector_emails = VectorEmail.objects.\
            filter(engagement=Engagement.objects.filter(campaign=campaigns))

    filter_status = [(k, v) for k, v in VectorEmail.STATE_CHOICES if k > 0]
    context = {'form': form,
               'client': client,
               'apage': 'clients',
               'page': page,
               'targetLists': targetLists,
               'campaigns': campaigns,
               'vector_emails': vector_emails,
               'sorting': sorting,
               'pg_size': pg_size,
               'filter_status': filter_status,
               'fs': f_status}

    if vector_emails:
        _filter['engagement__campaign__client'] = client.id
        extra_columns = ['engagement__id',
                         'engagement__name',
                         'engagement__campaign__id',
                         'engagement__campaign__name']
        vector_email_list_context = prepare_vector_email_list(request,
                                                              extra_columns,
                                                              _filter)
        context.update(vector_email_list_context)

    return render(request, 'client_edit.html', context)


@login_required
def emailServersList(request):
    page = __ordering(request, EmailServer, default='-id')

    return render(request, 'email_servers_list.html',
                  {'page': page, 'apage': 'email_servers',
                   'objects': page.object_list,
                   'sorting': request.GET.get('order_by')})


@login_required
def emailServerEdit(request, id=None):
    emailServer = None
    if request.method == 'GET':
        try:
            emailServer = EmailServer.objects.get(id=id)
            initial = {'es_id': emailServer.id,
                       'host': emailServer.host,
                       'port': emailServer.port,
                       'use_tls': emailServer.use_tls,
                       'login': emailServer.login,
                       'email_pw': emailServer.password,
                       'test_recipient': emailServer.test_recipient}
            form = EmailServerForm(initial=initial)
        except EmailServer.DoesNotExist:
            form = EmailServerForm()
    else:
        form = EmailServerForm(request.POST)
        if form.is_valid():
            es_id = form.cleaned_data.get('es_id')
            host = form.cleaned_data['host']
            port = form.cleaned_data['port']
            use_tls = form.cleaned_data['use_tls']
            login = form.cleaned_data['login']
            password = form.cleaned_data['email_pw']
            test_recipient = form.cleaned_data['test_recipient']

            emailServer, created = EmailServer.objects.\
                update_or_create(id=es_id,
                                 defaults={'host': host,
                                           'port': port,
                                           'use_tls': use_tls,
                                           'login': login,
                                           'password': password,
                                           'test_recipient': test_recipient})

            return redirect('/email-servers/list/')
        else:
            return JsonResponse(form.errors.as_json(), safe=False)

    return render(request, 'email_server_edit.html',
                  {'form': form, 'apage': 'email_servers',
                   'emailServer': emailServer})


@login_required
def emailTemplatesList(request):
    page = __ordering(request, EmailTemplate, default='-id')

    return render(request, 'email_templates_list.html',
                  {'page': page, 'apage': 'email_templates',
                   'objects': page.object_list,
                   'sorting': request.GET.get('order_by')})


@login_required
def emailTemplateEdit(request, id=None):
    emailTemplate = None
    if request.method == 'GET':
        try:
            emailTemplate = EmailTemplate.objects.get(id=id)
            initial = {'et_id': emailTemplate.id,
                       'name': emailTemplate.name,
                       'description': emailTemplate.description,
                       'from_header': emailTemplate.from_header,
                       'subject_header': emailTemplate.subject_header,
                       'template': emailTemplate.template}
            form = EmailTemplateForm(initial=initial)
        except EmailTemplate.DoesNotExist:
            form = EmailTemplateForm()
    else:
        form = EmailTemplateForm(request.POST)
        if form.is_valid():
            et_id = form.cleaned_data.get('et_id')
            name = form.cleaned_data['name']
            description = form.cleaned_data['description']
            from_header = form.cleaned_data['from_header']
            subject_header = form.cleaned_data['subject_header']
            template = form.cleaned_data.get('template', '').\
                                         replace('http://[#[url]#]', '[#[url]#]').\
                                         replace('https://[#[url]#]', '[#[url]#]').\
                                         replace('ftp://[#[url]#]', '[#[url]#]').\
                                         replace('news://[#[url]#]', '[#[url]#]')

            emailTemplate, created = EmailTemplate.objects.\
                update_or_create(id=et_id,
                                 defaults={'name': name,
                                           'description': description,
                                           'from_header': from_header,
                                           'subject_header': subject_header,
                                           'template': template})

            return redirect('/email-templates/list/')
        else:
            return JsonResponse(form.errors.as_json(), safe=False)

    target_list_view = dict(TargetList.objects.all().values_list('id',
                                                                 'nickname'))

    return render(request, 'email_template_edit.html',
                  {'form': form, 'apage': 'email_templates',
                   'emailTemplate': emailTemplate,
                   'target_lists': target_list_view})


@login_required
def email_template_get_variables(request):
    res = {'success': False}
    if request.method == 'POST':
        list_id = request.POST.get('list_id')
        target_list = TargetList.objects.get(id=list_id)
        res['data'] = ', '.join(['[#[%s]#]' % k[0] for k in
                                 TargetDatum.objects.filter(target__in=target_list.target.all()).
                                distinct('label').values_list('label')])
        res['success'] = True

    return JsonResponse(res, safe=False)


@login_required
def check_email_template_shortcodes(request):
    res = {'success': False, 'shortcode_errors': []}

    if request.method == 'POST':
        list_id = request.POST.get('list_id')
        template = request.POST.get('template')
        targets = TargetList.objects.get(id=list_id).target.all()
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
                    shortcode_errors.append('<span style="color: red;">Error:'
                                            ' Invalid shortcode "[#[{}]#]" in'
                                            ' use on line {}</span><br />'
                                            ''.format(each_shortcode, index))

        res['shortcode_errors'] = ''.join(shortcode_errors)
        res['success'] = True

    return JsonResponse(res, safe=False)


@login_required
def landingPagesList(request):
    _filter = {'is_redirect_page': False}
    page = __ordering(request, LandingPage, default='-id', _filter=_filter)

    return render(request, 'landing_pages_list.html',
                  {'page': page, 'apage': 'landing_pages',
                   'objects': page.object_list,
                   'sorting': request.GET.get('order_by')})


@login_required
def redirectPagesList(request):
    _filter = {'is_redirect_page': True}
    page = __ordering(request, LandingPage, default='-id', _filter=_filter)

    return render(request, 'landing_pages_list.html',
                  {'page': page, 'apage': 'redirect_pages',
                   'objects': page.object_list,
                   'sorting': request.GET.get('order_by')})


@login_required
def landingPageEdit(request, id=None, is_redirect_page=False):
    landingPage = None
    source = None
    if request.method == 'GET':
        try:
            landingPage = LandingPage.objects.get(id=id)
            initial = {'name': landingPage.name,
                       'description': landingPage.description,
                       'url': landingPage.url,
                       'landing_page_id': landingPage.id,
                       'is_redirect_page': landingPage.is_redirect_page,
                       'page_type': landingPage.page_type,
                       'scraper_user_agent': landingPage.scraper_user_agent}
            if is_redirect_page:
                form = RedirectPageForm(initial=initial)
            else:
                form = LandingPageForm(initial=initial)
            with open(landingPage.path, 'r') as f:
                source = f.read()
        except LandingPage.DoesNotExist:
            if is_redirect_page:
                form = RedirectPageForm()
            else:
                form = LandingPageForm()
        except TypeError:
            pass
        except IOError:
            pass
    else:
        is_changed = False
        if request.POST.get('refetch'):
            is_changed = True
        if is_redirect_page:
            form = RedirectPageForm(request.POST)
        else:
            form = LandingPageForm(request.POST)
        if form.is_valid():
            source = request.POST.get('template')
            name = form.cleaned_data['name']
            description = form.cleaned_data['description']
            url = form.cleaned_data.get('url')
            page_type = form.cleaned_data['page_type']
            is_redirect_page = form.cleaned_data.get('is_redirect_page')
            scraper_user_agent = form.cleaned_data.get('scraper_user_agent')
            try:
                landingPage = LandingPage.objects.get(id=id)
                if landingPage.url != url:
                    is_changed = True
                if not landingPage.path:
                    is_changed = True
                if landingPage.scraper_user_agent != scraper_user_agent:
                    is_changed = True
                landingPage.name = name
                landingPage.description = description
                landingPage.url = url
                landingPage.page_type = page_type
                landingPage.is_redirect_page = is_redirect_page
                landingPage.scraper_user_agent = scraper_user_agent

                # LandingPage HTML template form validation must come before
                # the LandingPage is saved to prevent the saving of an
                # invalid record. Checking for landingPage.path allows
                # LandingPages to be saved when page_type == 'page' and the
                # scraper hasn't finished yet.
                if source and landingPage.path and not is_redirect_page:
                    if detect_landing_page_form(source) is False:
                        form.fields['template'] = dict()
                        form.add_error('template',
                                       'Landing page form not found.')
                        return JsonResponse(form.errors.as_json(), safe=False)

                landingPage.save()

                if source and landingPage.path:
                    path = landingPage.path
                    with open(path, 'w') as f:
                        f.write(source.encode('utf-8'))
            except LandingPage.DoesNotExist:
                # LandingPage HTML template form validation for nonexistant
                # LandingPages must only occur if the prospective LandingPage's
                # page_type is 'manual', because 'page'-type LandingPages that
                # have not yet been scraped will still return templates and
                # those templates will not contain a valid HTML form.
                if source and not is_redirect_page:
                    if page_type == 'manual' and \
                            detect_landing_page_form(source) is False:
                        form.fields['template'] = dict()
                        form.add_error('template',
                                       'Landing page form not found.')
                        return JsonResponse(form.errors.as_json(), safe=False)

                landingPage = LandingPage.objects.\
                    create(name=name,
                           description=description,
                           url=url,
                           page_type=page_type,
                           is_redirect_page=is_redirect_page,
                           scraper_user_agent=scraper_user_agent)
                is_changed = True

            if is_changed and page_type == 'page':
                landingPage.path = None
                landingPage.status = 2
                landingPage.save()
                parse_page.delay(landingPage)
            elif page_type == 'manual':
                if landingPage.path is None:
                    filename = '%032x.html' % getrandbits(128)
                    dirname = '{}-{}'.format(landingPage.id,
                                             landingPage.date_created.\
                                                         strftime('%s'))
                    if is_redirect_page:
                        page_type_dir = 'redirect-pages'
                    else:
                        page_type_dir = 'landing-pages'
                    page_path = os.path.join('assets',
                                             page_type_dir,
                                             dirname,
                                             'html',
                                             filename)
                else:
                    page_path = landingPage.path
                if not os.path.exists(os.path.dirname(page_path)):
                    os.makedirs(os.path.dirname(page_path))
                with open(page_path, 'w') as f:
                    f.write(source.encode('utf-8'))
                landingPage.path = page_path
                landingPage.status = 1
                landingPage.save()
            elif page_type == 'url':
                landingPage.path = None
                landingPage.save()

            redirect_url = '/landing-pages/list/'
            if is_redirect_page:
                redirect_url = '/redirect-pages/list/'
            return redirect(redirect_url)
        else:
            return JsonResponse(form.errors.as_json(), safe=False)
    apage = 'landing_pages'
    if is_redirect_page:
        apage = 'redirect_pages'

    return render(request, 'landing_page_edit.html',
                  {'form': form, 'apage': apage,
                   'landingPage': landingPage,
                   'source': source})


@login_required
def schedulesList(request):
    page = __ordering(request, Schedule, default='-id')

    return render(request, 'schedules_list.html',
                  {'page': page, 'apage': 'schedules',
                   'objects': page.object_list,
                   'sorting': request.GET.get('order_by')})


@login_required
def scheduleEdit(request, id=None):
    schedule = None
    if request.method == 'GET':
        try:
            schedule = Schedule.objects.get(id=id)
            initial = {
                'schedule_id': schedule.id,
                'name': schedule.name,
                'description': schedule.description,
                'is_default': schedule.is_default,
                'interval': '000010',
                'excluded_dates': schedule.excluded_dates
            }
            form = ScheduleForm(initial=initial)
        except Schedule.DoesNotExist:
            form = ScheduleForm()
    else:
        form = ScheduleForm(request.POST)
        if form.is_valid():
            schedule_id = form.cleaned_data.get('schedule_id')
            name = form.cleaned_data['name']
            description = form.cleaned_data['description']
            is_default = form.cleaned_data['is_default']
            # interval = form.cleaned_data['interval']
            interval = 10
            excluded_dates = form.cleaned_data['excluded_dates']

            schedule, created = Schedule.objects.\
                update_or_create(id=schedule_id,
                                 defaults={'name': name,
                                           'description': description,
                                           'is_default': is_default,
                                           'interval': interval,
                                           'excluded_dates': excluded_dates})

            return redirect('/schedules/list/')
        else:
            return JsonResponse(form.errors.as_json(), safe=False)

    return render(request, 'schedule_edit.html',
                  {'form': form,
                   'apage': 'schedules',
                   'schedule': schedule})


@login_required
def targetsListList(request):
    _filter = ''
    if request.GET.get('client'):
        _filter = {'client': request.GET['client']}
    page = __ordering(request, TargetList, default='-id', _filter=_filter)

    return render(request, 'targets_list_list.html',
                  {'page': page, 'apage': 'target_lists',
                   'objects': page.object_list,
                   'sorting': request.GET.get('order_by'),
                   'clients': Client.objects.order_by('-id'),
                   'client': request.GET.get('client', 0)})


@login_required
@csrf_exempt
def targetListEdit(request, id=None, extend=None):
    target_list = None
    lt_action = 'create'
    clients = Client.objects.order_by('-id')
    if request.method == 'GET' and id:
        lt_action = 'modify' if not extend else 'extend'
        try:
            targetList = TargetList.objects.get(id=id)
            targets = []
            target_list = {}
            for t in targetList.target.order_by('id'):
                target_datum = {}
                targetDatum = TargetDatum.objects.filter(target=t,
                                                         target_list=targetList)
                for td in targetDatum:
                    target_datum.update({td.label: td.value})
                targets.append({'id': t.id,
                                'email': t.email,
                                'firstname': t.firstname,
                                'lastname': t.lastname,
                                'timezone': t.timezone,
                                'targetDatum': target_datum})
            if targetList.client:
                client = {'id': targetList.client.id,
                          'name': targetList.client.name}
            else:
                client = None
            target_list = {'id': targetList.id,
                           'nickname': targetList.nickname,
                           'description': targetList.description,
                           'client': client,
                           'targets': targets}
        except TargetList.DoesNotExist:
            raise Http404()
    elif request.method == 'POST':
        targets = request.POST.get('targets')
        json_targets = json.loads(targets)
        for tl in json_targets:
            try:
                client = Client.objects.get(id=tl.get('client'))
            except Client.DoesNotExist:
                client = None
            snipped_description = tl.get('description')[:100]
            targetList, createdtl = TargetList.objects.\
                update_or_create(id=tl.get('id'),
                                 defaults={'nickname': tl.get('nickname'),
                                           'description': snipped_description,
                                           'client': client})
            try:
                targetList.target.\
                    exclude(id__in=[i.get('id') for i in tl.get('targets')\
                                    if i.get('id')]).\
                    delete()
            except TargetList.DoesNotExist:
                pass
            for item in tl.get('targets'):
                if not item.get('email'):
                    continue
                target, created = Target.objects.\
                    update_or_create(
                        id=item.get('id'),
                        defaults={'email': item.get('email'),
                                  'firstname': item.get('firstname'),
                                  'lastname': item.get('lastname'),
                                  'timezone': item.get('timezone')})
                TargetDatum.objects.filter(target=target.id).delete()
                if 'targetDatum' in item:
                    for k, v in item['targetDatum'].iteritems():
                        TargetDatum.objects.create(label=k,
                                                   value=v,
                                                   target=target,
                                                   target_list=targetList)
                if created:
                    targetList.target.add(target)

    return render(request, 'targets_list_edit.html',
                  {'target_list': json.dumps(target_list),
                   'type': lt_action, 'clients': clients,
                   'apage': 'target_lists', 'tl': target_list})


@login_required
def vectorEmailList(request):
    extra_columns = ['engagement__campaign__client__id',
                     'engagement__campaign__client__name',
                     'engagement__campaign__id',
                     'engagement__campaign__name',
                     'engagement__id',
                     'engagement__name']

    vector_email_list_context = prepare_vector_email_list(request,
                                                          extra_columns,
                                                          {})
    context = {'apage': 'email_log'}
    context.update(vector_email_list_context)

    return render(request, 'email_log.html', context)


@login_required
def scraperUserAgentEdit(request, id=None):
    scraper_user_agent = None

    if request.method == 'GET':
        try:
            scraper_user_agent = ScraperUserAgent.objects.get(id=id)
            initial = {
                'sua_id': scraper_user_agent.id,
                'name': scraper_user_agent.name,
                'user_agent_data': scraper_user_agent.user_agent_data
            }
            form = ScraperUserAgentForm(initial=initial)
        except ScraperUserAgent.DoesNotExist:
            form = ScraperUserAgentForm()
    else:
        form = ScraperUserAgentForm(request.POST)
        if form.is_valid():
            sua_id = form.cleaned_data.get('sua_id')
            user_agent_data = form.cleaned_data['user_agent_data']
            ScraperUserAgent.objects.\
                update_or_create(id=sua_id,
                                 defaults={'name': form.cleaned_data['name'],
                                           'user_agent_data': user_agent_data})
            return redirect('/scraper-user-agents/list/')
        else:
            return JsonResponse(form.errors.as_json(), safe=False)

    return render(request, 'scraper_user_agent_edit.html',
                  {'form': form,
                   'apage': 'scraper_user_agents',
                   'scraper_user_agent': scraper_user_agent})


@login_required
def scraperUserAgentsList(request):
    page = __ordering(request, ScraperUserAgent, default='-id')

    return render(request, 'scraper_user_agents_list.html',
                  {'page': page, 'apage': 'scraper_user_agents',
                   'objects': page.object_list,
                   'sorting': request.GET.get('order_by')})


@login_required
def slackHookEdit(request, id=None):
    slack_hook = None

    if request.method == 'GET':
        try:
            slack_hook = SlackHook.objects.get(id=id)
            initial = {
                'sh_id': slack_hook.id,
                'webhook_url': slack_hook.webhook_url,
                'description': slack_hook.description
            }
            form = SlackHookForm(initial=initial)
        except SlackHook.DoesNotExist:
            form = SlackHookForm()
    else:
        form = SlackHookForm(request.POST)
        if form.is_valid():
            sh_id = form.cleaned_data.get('sh_id')
            description = form.cleaned_data['description']
            SlackHook.objects.update_or_create(
                id=sh_id,
                defaults={
                    'webhook_url': form.cleaned_data['webhook_url'],
                    'description': description
                }
            )
            return redirect('/slack-hooks/list/')
        else:
            return JsonResponse(form.errors.as_json(), safe=False)

    return render(request, 'slack_hook_edit.html',
                  {'form': form,
                   'apage': 'slack_hooks',
                   'slack_hook': slack_hook})


@login_required
def slackHooksList(request):
    page = __ordering(request, SlackHook, default='-id')

    return render(request, 'slack_hooks_list.html',
                  {'page': page, 'apage': 'slack_hooks',
                   'objects': page.object_list,
                   'sorting': request.GET.get('order_by')})


@login_required
def openRedirectEdit(request, id=None):
    open_redirect = None

    if request.method == 'GET':
        try:
            open_redirect = OpenRedirect.objects.get(id=id)
            initial = {
                'or_id': open_redirect.id,
                'url': open_redirect.url
            }
            form = OpenRedirectForm(initial=initial)
        except OpenRedirect.DoesNotExist:
            form = OpenRedirectForm()
    else:
        form = OpenRedirectForm(request.POST)
        if form.is_valid():
            or_id = form.cleaned_data.get('or_id')
            url = form.cleaned_data['url']
            OpenRedirect.objects.\
                update_or_create(id=or_id,
                                 defaults={'url': url})
            return redirect('/open-redirects/list/')
        else:
            return JsonResponse(form.errors.as_json(), safe=False)

    return render(request, 'open_redirect_edit.html',
                  {'form': form,
                   'apage': 'open_redirects',
                   'open_redirect': open_redirect})


@login_required
def openRedirectsList(request):
    page = __ordering(request, OpenRedirect, default='-id')

    return render(request, 'open_redirects_list.html',
                  {'page': page, 'apage': 'open_redirects',
                   'objects': page.object_list,
                   'sorting': request.GET.get('order_by')})


@login_required
def phishingDomainEdit(request, id=None):
    phishing_domain = None

    if request.method == 'GET':
        try:
            phishing_domain = PhishingDomain.objects.get(id=id)
            initial = {
                'pd_id': phishing_domain.id,
                'protocol': phishing_domain.protocol,
                'domain_name': phishing_domain.domain_name
            }
            form = PhishingDomainForm(initial=initial)
        except PhishingDomain.DoesNotExist:
            form = PhishingDomainForm()
    else:
        form = PhishingDomainForm(request.POST)
        if form.is_valid():
            pd_id = form.cleaned_data.get('pd_id')
            protocol = form.cleaned_data['protocol'].strip()
            domain_name = form.cleaned_data['domain_name'].strip()
            PhishingDomain.objects.\
                update_or_create(id=pd_id,
                                 defaults={'protocol': protocol,
                                           'domain_name': domain_name})
            return redirect('/phishing-domains/list/')
        else:
            return JsonResponse(form.errors.as_json(), safe=False)

    return render(request, 'phishing_domain_edit.html',
                  {'form': form,
                   'apage': 'phishing_domains',
                   'phishing_domain': phishing_domain})


@login_required
def phishingDomainsList(request):
    page = __ordering(request, PhishingDomain, default='-id')

    return render(request, 'phishing_domains_list.html',
                  {'page': page, 'apage': 'phishing_domains',
                   'objects': page.object_list,
                   'sorting': request.GET.get('order_by')})


@login_required
def siteSettingsEdit(request):
    site_settings = None

    if request.method == 'GET':
        site_settings = SiteSettings.load()
        initial = {
            'public_ip': site_settings.public_ip
        }
        form = SiteSettingsForm(initial=initial)
    else:
        form = SiteSettingsForm(request.POST)
        if form.is_valid():
            public_ip = form.cleaned_data['public_ip']
            SiteSettings.objects.all().update(**{'public_ip': public_ip})
            return redirect('/site-settings/edit/')
        else:
            return JsonResponse(form.errors.as_json(), safe=False)

    return render(request, 'site_settings_edit.html',
                  {'form': form,
                   'apage': 'site_settings',
                   'site_settings': site_settings})


@login_required
def oAuthConsumerEdit(request, id=None):
    oauth_consumer = None

    if request.method == 'GET':
        try:
            oauth_consumer = OAuthConsumer.objects.get(id=id)
            initial = {
                'oac_id': oauth_consumer.id,
                'name': oauth_consumer.name,
                'description': oauth_consumer.description,
                'client_id': oauth_consumer.client_id,
                'client_secret': oauth_consumer.client_secret,
                'scope': oauth_consumer.scope,
                'callback_url': oauth_consumer.callback_url,
                'bounce_url': oauth_consumer.bounce_url,
            }
            form = OAuthConsumerForm(initial=initial)
        except OAuthConsumer.DoesNotExist:
            form = OAuthConsumerForm()
    else:
        form = OAuthConsumerForm(request.POST)
        if form.is_valid():
            oac_id = form.cleaned_data.get('oac_id')
            name = form.cleaned_data.get('name')
            description = form.cleaned_data.get('description')
            client_id = form.cleaned_data.get('client_id')
            client_secret = form.cleaned_data.get('client_secret')
            scope = form.cleaned_data.get('scope')
            callback_url = form.cleaned_data.get('callback_url')
            bounce_url = form.cleaned_data.get('bounce_url')

            OAuthConsumer.objects.update_or_create(
                id=oac_id,
                defaults={
                    'name': name,
                    'description': description,
                    'client_id': client_id,
                    'client_secret': client_secret,
                    'scope': scope,
                    'callback_url': callback_url,
                    'bounce_url': bounce_url})
            return redirect('/oauth-consumers/list/')
        else:
            return JsonResponse(form.errors.as_json(), safe=False)

    return render(request, 'oauth_consumer_edit.html',
                  {'form': form,
                   'apage': 'oauth_consumers',
                   'oauth_consumer': oauth_consumer})


@login_required
def oAuthConsumersList(request):
    page = __ordering(request, OAuthConsumer, default='-id')

    return render(request, 'oauth_consumers_list.html',
                  {'page': page, 'apage': 'oauth_consumers',
                   'objects': page.object_list,
                   'sorting': request.GET.get('order_by')})


@login_required
def oAuthResultEdit(request, id=None):
    oauth_result = None
    if request.method == 'GET':
        try:
            oauth_result = OAuthResult.objects.get(id=id)
            initial = {'oar_id': oauth_result.id,
                       'email': oauth_result.email,
                       'target': oauth_result.target,
                       'oauth_engagement': oauth_result.oauth_engagement,
                       'consumer': oauth_result.consumer,
                       'ip': oauth_result.ip,
                       'timestamp': oauth_result.timestamp,
                       'userAgent': oauth_result.userAgent}
            form = OAuthResultForm(initial=initial)
        except OAuthResult.DoesNotExist:
            form = OAuthResultForm()
        for each_field in form.fields:
            form.fields[each_field].widget.attrs['readonly'] = 'readonly'
            form.fields[each_field].widget.attrs['disabled'] = 'disabled'
    else:
        return redirect('/oauth-results/list/')

    return render(request, 'oauth_result_edit.html',
                  {'form': form,
                   'oauth_result': oauth_result,
                   'apage': 'oauth_results'})


@login_required
def oAuthResultsList(request):
    page = __ordering(request, OAuthResult, default='-id')
    pg_size = request.GET.get('pg_size', 25)

    return render(request, 'oauth_results_list.html',
                  {'page': page, 'apage': 'oauth_results',
                   'objects': page.object_list,
                   'sorting': request.GET.get('order_by'),
                   'pg_size': pg_size})


@login_required
def plunderEdit(request, id=None):
    plunder = None
    if request.method == 'GET':
        try:
            plunder = Plunder.objects.get(id=id)
            initial = {'plunder_id': plunder.id,
                       'oauth_result': plunder.oauth_result,
                       'path': plunder.path,
                       'file_id': plunder.file_id,
                       'filename': plunder.filename,
                       'mimetype': plunder.mimetype,
                       'last_modified': plunder.last_modified,
                       'data': plunder.data}
            form = PlunderForm(initial=initial)
        except Plunder.DoesNotExist:
            form = PlunderForm()
        for each_field in form.fields:
            form.fields[each_field].widget.attrs['readonly'] = 'readonly'
            form.fields[each_field].widget.attrs['disabled'] = 'disabled'

    else:
        return redirect('/plunder/list/')

    return render(request, 'plunder_edit.html',
                  {'form': form,
                   'plunder': plunder,
                   'apage': 'plunder'})


@login_required
def plunderList(request):
    plunder_list_context = prepare_plunder_list(request, {})
    context = {'apage': 'plunder'}
    context.update(plunder_list_context)

    return render(request, 'plunder_log.html', context)


@login_required
def shoalScrapeCredsEdit(request, id=None):
    shoalscrape_creds = None

    if request.method == 'GET':
        try:
            shoalscrape_creds = ShoalScrapeCreds.objects.get(id=id)
            initial = {
                'shoalscrape_creds_id': shoalscrape_creds.id,
                'name': shoalscrape_creds.name,
                'username': shoalscrape_creds.username,
                'password': shoalscrape_creds.password,
                'scraper_user_agent': shoalscrape_creds.scraper_user_agent
            }
            form = ShoalScrapeCredsForm(initial=initial)
        except ShoalScrapeCreds.DoesNotExist:
            form = ShoalScrapeCredsForm()
    else:
        form = ShoalScrapeCredsForm(request.POST)
        if form.is_valid():
            shoalscrape_creds_id = form.cleaned_data.get('shoalscrape_creds_id')
            name = form.cleaned_data['name']
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            scraper_user_agent = form.cleaned_data['scraper_user_agent']
            ShoalScrapeCreds.objects.update_or_create(
                id=shoalscrape_creds_id,
                defaults={'name': name,
                          'username': username,
                          'password': password,
                          'scraper_user_agent': scraper_user_agent})
            return redirect('/shoalscrape-creds/list/')
        else:
            return JsonResponse(form.errors.as_json(), safe=False)

    return render(request, 'shoalscrape_creds_edit.html',
                  {'form': form,
                   'apage': 'shoalscrape_creds',
                   'shoalscrape_creds': shoalscrape_creds})


@login_required
def shoalScrapeCredsList(request):
    page = __ordering(request, ShoalScrapeCreds, default='-id')

    return render(request, 'shoalscrape_creds_list.html',
                  {'page': page, 'apage': 'shoalscrape_creds',
                   'objects': page.object_list,
                   'sorting': request.GET.get('order_by')})


@login_required
def shoalScrapeTaskEdit(request, id=None):
    shoalscrape_task = None
    csv = '#'

    if request.method == 'GET':
        try:
            shoalscrape_task = ShoalScrapeTask.objects.get(id=id)
            initial = {
                'shoalscrape_task_id': shoalscrape_task.id,
                'shoalscrape_creds': shoalscrape_task.shoalscrape_creds,
                'company': shoalscrape_task.company,
                'domain': shoalscrape_task.domain,
                'company_linkedin_id': shoalscrape_task.company_linkedin_id,
                'last_started_at': shoalscrape_task.last_started_at,
                'path': shoalscrape_task.path,
            }
            form = ShoalScrapeTaskForm(initial=initial)
            company = shoalscrape_task.company.lower().replace(' ', '_')
            csv = '/assets/shoalscrape/{}/{}_master_list.csv'.format(id,
                                                                     company)
        except ShoalScrapeTask.DoesNotExist:
            form = ShoalScrapeTaskForm()
        for each_field in ('last_started_at', 'path'):
            form.fields[each_field].widget.attrs['readonly'] = 'readonly'
            form.fields[each_field].widget.attrs['disabled'] = 'disabled'
    else:
        form = ShoalScrapeTaskForm(request.POST)
        if form.is_valid():
            shoalscrape_task_id = form.cleaned_data.get('shoalscrape_task_id')

            if shoalscrape_task_id:
                try:
                    shoalscrape_task = ShoalScrapeTask.objects.\
                        get(id=shoalscrape_task_id)
                    if shoalscrape_task.state == ShoalScrapeTask.IN_PROGRESS:
                        shoalscrape_task.set_state(ShoalScrapeTask.PAUSED)
                        shoalscrape_task.terminate_task()
                except Exception as e:
                    logger.info('POST for existing ShoalScrapeTask with ID {}'
                                ' raised an exception when stopping its task:'
                                ' {}'.format(shoalscrape_task.id, str(e)))

            shoalscrape_creds = form.cleaned_data.get('shoalscrape_creds')
            company = form.cleaned_data.get('company')
            domain = form.cleaned_data.get('domain')
            company_linkedin_id = form.cleaned_data.get('company_linkedin_id')

            shoalscrape_task, _ = ShoalScrapeTask.objects.update_or_create(
                id=shoalscrape_task_id,
                defaults={'shoalscrape_creds': shoalscrape_creds,
                          'company': company,
                          'domain': domain,
                          'company_linkedin_id': company_linkedin_id})

            shoalscrape_task.save()
            shoalscrape_task.set_log_file_path()
            shoalscrape_task.initialize_task()

            return redirect('/shoalscrape-tasks/list/')
        else:
            return JsonResponse(form.errors.as_json(), safe=False)

    return render(request, 'shoalscrape_task_edit.html',
                  {'form': form,
                   'apage': 'shoalscrape_tasks',
                   'shoalscrape_task': shoalscrape_task,
                   'csv_url': csv})


@login_required
def shoalScrapeTasksList(request):
    page = __ordering(request, ShoalScrapeTask, default='-id')

    return render(request, 'shoalscrape_tasks_list.html',
                  {'page': page, 'apage': 'shoalscrape_tasks',
                   'objects': page.object_list,
                   'sorting': request.GET.get('order_by')})


def prepare_vector_email_list(request, extra_columns, _filter):
    sorting = request.GET.get('order_by', '')
    pg_size = request.GET.get('pg_size', 25)
    f_status = request.GET.get('filter_status')
    _filter.update({'state__gt': -1})
    if f_status:
        _filter.pop('state__gt')
        _filter['state'] = f_status

    page = __ordering(request, VectorEmail, default='send_at', _filter=_filter)

    basic_columns = ['id', 'state', 'target__email',
                     'target__targetlist', 'send_at', 'target']
    columns = basic_columns + extra_columns

    # Due to the ManyToManyField between Targets and TargetLists, the queryset
    # can't have its own `values` method called, to avoid duplicate entries.
    # ref: https://docs.djangoproject.com/en/1.8/ref/models/querysets/#values
    vector_emails = list()
    for vector_email in page.object_list:
        single_ve_queryset = VectorEmail.objects.filter(id=vector_email.id)
        # If extend(values) is used instead of append(values[0]), the duplicate
        # entries from extra ManyToManyField relations would be added here.
        vector_emails.append(single_ve_queryset.values(*columns)[0])

    for each in vector_emails:
        vector_email = VectorEmail.objects.get(id=each['id'])
        engagement = vector_email.engagement
        target = vector_email.target
        target_list = target.targetlist_set.filter(engagement=engagement).last()
        each['engagement__status'] = engagement.status
        each['target__id'] = target.id
        each['target__timezone'] = target.get_timezone()
        each['target__targetlist_set__get__id'] = target_list.id
        each['target__targetlist_set__get__nickname'] = target_list.nickname
        each['is_oauth'] = engagement.is_oauth
        if each['is_oauth']:
            oa_result = vector_email.targeted_oauth_result
            if oa_result is not None:
                each['oauth_granted'] = True
                each['targeted_oauth_result_id'] = oa_result.id
            else:
                each['oauth_granted'] = False

    filter_status = [(k, v) for k, v in VectorEmail.STATE_CHOICES if k > 0]
    vector_email_list_context = {'page': page,
                                 'vector_emails': vector_emails,
                                 'sorting': sorting,
                                 'pg_size': pg_size,
                                 'filter_status': filter_status,
                                 'fs': f_status}

    return vector_email_list_context


def prepare_plunder_list(request, _filter):
    sorting = request.GET.get('order_by', '')
    pg_size = request.GET.get('pg_size', 25)

    page = __ordering(request, Plunder, default='-id', _filter=_filter)

    columns = ['id', 'oauth_result', 'filename', 'mimetype', 'last_modified']
    plunder = page.object_list.values(*columns)

    for each in plunder:
        obj = Plunder.objects.get(id=each['id'])
        each['oauth_result'] = obj.oauth_result

    filter_status = [each for each in Plunder.objects.order_by('-id')]
    plunder_list_context = {'page': page,
                            'plunder': plunder,
                            'sorting': sorting,
                            'pg_size': pg_size,
                            'filter_status': filter_status}

    return plunder_list_context


@login_required
def start_stop_shoalscrape_task(request):
    shoalscrape_task_id = int(request.POST.get('shoalscrape_task_id', None))
    try:
        shoalscrape_task = ShoalScrapeTask.objects.get(id=shoalscrape_task_id)

        active_tasks = ShoalScrapeTask.objects.filter(
            Q(periodic_task__enabled=True) | Q(state=ShoalScrapeTask.IN_PROGRESS)
        ).exclude(id=shoalscrape_task_id)

        if active_tasks.exists():
            ids = [each.id for each in active_tasks]
            error_template = ('Started while other ShoalScrape tasks '
                             'were running: {}'.format(ids))
            logger.info('[ ! ] ' + error_template)
            # Doesn't call shoalscrape_task.terminate_task here. Because of
            # Celery weirdness with task termination, that should only be used
            # if the task is known to be running -- as with pause or right
            # after calling set_state(ShoalScrapeTask.ERROR) from inside the
            # worker running the task.
            shoalscrape_task.set_state(ShoalScrapeTask.ERROR)
            shoalscrape_task.error = error_template
            shoalscrape_task.save()
            return JsonResponse([error_template], safe=False)

        shoalscrape_task.toggle_task()
        state, error = shoalscrape_task.status
        data = {'state': state, 'error': error}
    except ShoalScrapeTask.DoesNotExist:
        error_template = ('ShoalScrapeTask does not exist: '
                          '{}'.format(request.POST.get('shoalscrape_task_id',
                                                       None)))
        logger.info(error_template)
        data = [error_template]

    return JsonResponse(data, safe=False)


@login_required
@csrf_exempt
def clientDelete(request, id):
    return deleteObjectMethod(request, id, Client, 'clients')


@login_required
@csrf_exempt
def campaignDelete(request, id):
    return deleteObjectMethod(request, id, Campaign, 'campaigns')


@login_required
@csrf_exempt
def engagementDelete(request, id):
    return deleteObjectMethod(request, id, Engagement, 'engagements')


@login_required
@csrf_exempt
def shoalScrapeTaskDelete(request, id):
    return deleteObjectMethod(request, id, ShoalScrapeTask, 'shoalscrape-tasks')


@login_required
@csrf_exempt
def shoalScrapeCredsDelete(request, id):
    return deleteObjectMethod(request, id, ShoalScrapeCreds, 'shoalscrape-creds')


@login_required
@csrf_exempt
def emailServerDelete(request, id):
    return deleteObjectPost(request, id, EmailServer)


@login_required
@csrf_exempt
def emailTemplateDelete(request, id):
    return deleteObjectPost(request, id, EmailTemplate)


@login_required
@csrf_exempt
def landingPageDelete(request, id):
    return deleteObjectPost(request, id, LandingPage)


@login_required
@csrf_exempt
def redirectPageDelete(request, id):
    return deleteObjectPost(request, id, LandingPage)


@login_required
@csrf_exempt
def scheduleDelete(request, id):
    return deleteObjectPost(request, id, Schedule)


@login_required
@csrf_exempt
def scheduleWindowDelete(request, id):
    return deleteObjectPost(request, id, ScheduleWindow)


@login_required
@csrf_exempt
def userDelete(request, id):
    return deleteObjectPost(request, id, User)


@login_required
@csrf_exempt
def targetListDelete(request, id):
    try:
        # The API does not delete all of a TargetList's Targets upon deletion.
        TargetList.objects.get(id=id).target.all().delete()
    except TargetList.DoesNotExist:
        return JsonResponse({'success': False}, safe=False)

    return deleteObjectPost(request, id, TargetList)


@login_required
@csrf_exempt
def vectorEmailDelete(request, id):
    return deleteObjectPost(request, id, VectorEmail)


@login_required
@csrf_exempt
def slackHookDelete(request, id):
    return deleteObjectPost(request, id, SlackHook)


@login_required
@csrf_exempt
def scraperUserAgentDelete(request, id):
    return deleteObjectPost(request, id, ScraperUserAgent)


@login_required
@csrf_exempt
def openRedirectDelete(request, id):
    return deleteObjectPost(request, id, OpenRedirect)


@login_required
@csrf_exempt
def phishingDomainDelete(request, id):
    return deleteObjectPost(request, id, PhishingDomain)


@login_required
@csrf_exempt
def oAuthConsumerDelete(request, id):
    return deleteObjectPost(request, id, OAuthConsumer)


@login_required
@csrf_exempt
def oAuthResultDelete(request, id):
    return deleteObjectPost(request, id, OAuthResult)


@login_required
@csrf_exempt
def plunderDelete(request, id):
    return deleteObjectPost(request, id, Plunder)


def __convert_target_list_order_by_fields(order_by):
    """
    This function converts front-end-template-derived sorting strings, such as:
        'nickname'
        'email'
        'password'
    into strings consumable by TargetList's queryset.order_by, such as:
        'nickname'
        'target__email'
        'target__vector_email__result_event__password'
    """

    order_by = order_by.split(',')

    tl_fields = ['nickname', '-nickname']
    target_fields = ['email', 'firstname', 'lastname']
    target_fields_ = ['-email', '-firstname', '-lastname']
    result_event_fields = ['event_type', 'timestamp', 'userAgent', 'ip',
                           'login', 'password', 'raw_data']
    result_event_fields_ = ['-event_type', '-timestamp',
                            '-userAgent', '-ip', '-login', '-password',
                            '-raw_data']

    order_by_target_list = [i for i in order_by if i in tl_fields]
    order_by_target = ['target__%s' % i for i in order_by
                       if i in target_fields]
    order_by_target_ = ['-target__%s' % i[1:] for i in order_by
                        if i in target_fields_]
    order_by_result_event = ['target__vector_email__result_event__%s' % i
                             for i in order_by if i in result_event_fields]
    order_by_result_event_ = ['-target__vector_email__result_event__%s' % i[1:]
                              for i in order_by if i in result_event_fields_]

    if order_by_target:
        order_by_target_list.extend(order_by_target)
    if order_by_target_:
        order_by_target_list.extend(order_by_target_)
    if order_by_result_event:
        order_by_target_list.extend(order_by_result_event)
    if order_by_result_event_:
        order_by_target_list.extend(order_by_result_event_)
    return order_by_target_list


@login_required
def report(request, engagement_id):
    # Keeping sorting and order_by separate avoids altering context.
    # Here we make a copy of sorting and ensure that -timestamp is the default.
    sorting = request.GET.get('order_by', '')
    order_by = add_default_ordering(sorting, '-timestamp')

    f_target = request.GET.get('filter_target')
    f_status = request.GET.get('filter_status')
    order_by_target_list = __convert_target_list_order_by_fields(order_by)
    engagement = Engagement.objects.get(id=engagement_id)
    statistics = engagement.get_result_statistics()

    filters = {'target__vector_email__engagement': engagement_id,
               'target__vector_email__result_event__event_type__gt': 0}

    if f_target:
        filters['target__email'] = f_target

    if f_status:
        # Status 0 is intended to clear status tracking, but the filter_status
        # query parameter isn't removed when it's set to 0; hence, ignore it.
        if f_status == "0":
            pass
        else:
            filters.pop('target__vector_email__result_event__event_type__gt')
            filters['target__vector_email__result_event__event_type'] = f_status

    target_lists = TargetList.objects.filter(**filters).\
        order_by(*order_by_target_list)

    page = request.GET.get('page', 1)
    paginator = Paginator(target_lists, 100)
    page = paginator.page(page)

    results = page.object_list.\
        values('nickname', 'target__email',
               'target__firstname',
               'target__lastname',
               'target__vector_email__result_event__id',
               'target__vector_email__result_event__event_type',
               'target__vector_email__result_event__timestamp',
               'target__vector_email__result_event__userAgent',
               'target__vector_email__result_event__ip',
               'target__vector_email__result_event__login',
               'target__vector_email__result_event__password',
               'target__vector_email__result_event__raw_data')

    # ManyToManyFields can insert duplicate entries into queryset.values
    # results, so they must be pruned.
    # ref: https://docs.djangoproject.com/en/1.8/ref/models/querysets/#values
    found_result_event_ids = list()
    deduplicated_results = list()
    for result in results:
        # If the email has been encountered and the target list doesn't have
        # the same ID, then the target is in more than one target list in this
        # engagement. Even though it was sent only one email, the extra copies
        # of its Target:TargetList MTM relationship should be ignored.
        if result['target__vector_email__result_event__id'] in found_result_event_ids:
            continue
        else:
            found_result_event_ids.append(result['target__vector_email__result_event__id'])
            deduplicated_results.append(result)

    target_lists_all = TargetList.objects.\
        filter(target__vector_email__engagement=engagement_id,
               target__vector_email__result_event__event_type__gt=0)

    filter_target = [ft['target__email'] for ft in target_lists_all.
                     values('target__email').distinct()]
    filter_status = [(k, v) for k, v in ResultEvent.CHOICES if k > 0]

    context = {'page': page,
               'objects': deduplicated_results,
               'sorting': sorting,
               'filter_target': filter_target,
               'filter_status': filter_status,
               'ft': f_target,
               'fs': f_status,
               'statistics': statistics,
               'engagement': engagement}

    return render(request, 'report.html', context)


@login_required
def serve_campaign_csv_report(request, campaign_id):
    with BytesIO() as csv_buffer:
        csv_writer = csv.writer(csv_buffer)
        csv_writer.writerow(['engagement_id',
                             'engagement_name',
                             'email',
                             'email_template',
                             'engagement_domain',
                             'engagement_url_path',
                             'result'])
        campaign = Campaign.objects.get(id=campaign_id)
        for engagement in campaign.engagement_set.all():
            for vector_email in engagement.vector_email.order_by('id'):
                phishing_results = vector_email.result_event.order_by('-event_type')
                if len(phishing_results) == 0:
                    highest_result = 'NONE'
                else:
                    highest_result = phishing_results.first().get_event_type_display()
                engagement_name = engagement.name.encode('utf8', 'ignore')
                csv_writer.writerow([engagement.id,
                                     engagement_name,
                                     vector_email.target.email,
                                     engagement.email_template.name,
                                     engagement.domain.domain_name,
                                     engagement.path,
                                     highest_result])
        csv_buffer.seek(0)
        response = HttpResponse(csv_buffer.read(), content_type="text/csv")
        campaign_name = campaign.name.encode('utf8', 'ignore')
        disposition = 'attachment; filename=campaign_{}_{}.csv'.format(campaign.id,
                                                                       campaign_name)
        response['Content-Disposition'] = disposition
        return response


@login_required
def serve_engagement_csv_report(request, engagement_id):
    with BytesIO() as csv_buffer:
        csv_writer = csv.writer(csv_buffer)
        csv_writer.writerow(['engagement_id',
                             'engagement_name',
                             'email',
                             'email_template',
                             'engagement_domain',
                             'engagement_url_path',
                             'result'])
        engagement = Engagement.objects.get(id=engagement_id)
        for vector_email in engagement.vector_email.order_by('id'):
            phishing_results = vector_email.result_event.order_by('-event_type')
            if len(phishing_results) == 0:
                highest_result = 'NONE'
            else:
                highest_result = phishing_results.first().get_event_type_display()
            engagement_name = engagement.name.encode('utf8', 'ignore')
            csv_writer.writerow([engagement.id,
                                 engagement_name,
                                 vector_email.target.email,
                                 engagement.email_template.name,
                                 engagement.domain.domain_name,
                                 engagement.path,
                                 highest_result])
        csv_buffer.seek(0)
        response = HttpResponse(csv_buffer.read(), content_type="text/csv")
        disposition = 'attachment; filename=engagement_{}_{}.csv'.format(engagement.id,
                                                                         engagement.name)
        response['Content-Disposition'] = disposition
        return response


@csrf_exempt
def check_landing_page_state(request):
    if request.method == 'POST':
        ids_list = request.POST.getlist('ids[]')
        landing_pages = list(LandingPage.objects.filter(id__in=ids_list).
                             values_list('id', 'path', 'status'))
        return JsonResponse(landing_pages, safe=False)

    return JsonResponse({'error': 'no POST'})


@csrf_exempt
def check_engagement_status(request):
    if request.method == 'POST':
        ids_list = request.POST.getlist('ids[]')
        engagements = [{'id': engagement.id, 'status': engagement.status,
                        'statistics': engagement.get_result_statistics()}
                       for engagement in Engagement.objects.filter(id__in=ids_list)]
        return JsonResponse(engagements, safe=False)

    return JsonResponse({'error': 'no POST'})


@csrf_exempt
def check_engagement_status_campaign(request):
    if request.method == 'POST':
        ids_list = request.POST.getlist('ids[]')
        campaigns = [{'id': campaign.id, 'status': campaign.status}
                     for campaign in Campaign.objects.filter(id__in=ids_list)]
        return JsonResponse(campaigns, safe=False)

    return JsonResponse({'error': 'no POST'})


@csrf_exempt
def check_shoalscrape_task_status(request):
    if request.method == 'POST':
        ids_list = request.POST.getlist('ids[]')
        shoalscrape_tasks = [{'id': shoalscrape_task.id, 'status': shoalscrape_task.status}
                       for shoalscrape_task in ShoalScrapeTask.objects.filter(id__in=ids_list)]
        return JsonResponse(shoalscrape_tasks, safe=False)

    return JsonResponse({'error': 'no POST'})


@csrf_exempt
@login_required
def check_email(request):
    host = request.POST.get('host')
    port = request.POST.get('port')
    login = request.POST.get('login')
    password = request.POST.get('email_pw')
    use_tls = request.POST.get('use_tls')
    test_recipient = request.POST.get('test_recipient')
    all_check = all([host, port, login, password, use_tls, test_recipient])
    use_tls = True if use_tls == 'true' else False

    if all_check:
        emailBackend = EmailBackend(host=host, port=int(port), username=login,
                                    password=password, use_tls=use_tls)

        mbody = 'if you received this email - email settings are correct'
        try:
            EmailMessage('Test email', mbody, login, [test_recipient],
                         connection=emailBackend).send()
            data = {'success': True, 'message': 'Email settings are correct'}
        except Exception as e:
            data = {'success': False, 'message': str(e)}
    else:
        data = {'success': False, 'message': 'All fields are required'}
    return JsonResponse(data, safe=False)


@csrf_exempt
@login_required
def check_domain(request):
    protocol = request.POST.get('protocol')
    domain_name = request.POST.get('domain_name')
    ip = None

    try:
        sb_ip = SiteSettings.load().public_ip
    except (SiteSettings.DoesNotExist, AttributeError):
        sb_ip = None
    # Also covers the case where the public_ip setting is null.
    if sb_ip is None:
        sb_ip = '127.0.0.1'

    if not protocol:
        data = {'success': False, 'message': 'Enter a protocol to check.'}
        return JsonResponse(data, safe=False)

    if domain_name:
        try:
            ping_request = urllib2.Request('{}://{}'.format(protocol,
                                                            domain_name))
            response = urllib2.urlopen(ping_request,
                                       timeout=settings.PING_TIMEOUT)
            ip = gethostbyname(urlparse(response.geturl()).hostname)
        except urllib2.HTTPError as e:
            ip = gethostbyname(urlparse(e.geturl()).hostname)
        except urllib2.URLError as e:
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
                error_message = 'Domain name not found: {}'.format(str(e))
                logger.info('check_domain failure:'
                            '\n    e1: {}\n    e2: {}'.format(str(e), str(e2)))
                data = {'success': False, 'message': error_message}

        if ip is not None:
            if ip == sb_ip:
                data = {'success': True,
                        'message': 'Server exists at {} and matches Sandbar'
                                   ' host IP at {}'.format(ip, sb_ip)}
            else:
                data = {'success': False,
                        'message': 'Server exists at {} and does not match'
                                   ' Sandbar host IP at {}'.format(ip, sb_ip)}
    else:
        data = {'success': False, 'message': 'Enter a domain name to check.'}

    return JsonResponse(data, safe=False)


@login_required
def targetListByCampaign(request, campaign_id):
    try:
        campaign = Campaign.objects.get(id=campaign_id)
        targetList = TargetList.objects.filter(client=campaign.client)
        jsonTargetList = [{'name': tl.nickname,
                           'id': tl.id} for tl in targetList]
    except Campaign.DoesNotExist:
        data = {'success': False}
    data = {'success': True,
            'targetList': jsonTargetList}
    return JsonResponse(data)


@login_required
def emailTemplatePreview(request, id):
    try:
        email_template = EmailTemplate.objects.get(id=id)
        data = {'success': True, 'template': email_template.template}
    except EmailTemplate.DoesNotExist:
        data = {'success': False}
    return JsonResponse(data, safe=False)


@csrf_exempt
@login_required
def decode_quopri(request):
    template = request.POST.get('template', '')
    try:
        decoded_template = template.encode('ascii', 'ignore').decode('quopri')
        data = {'success': True, 'template': decoded_template, 'error': None}
        # If the template is incorrectly decoded by the quopri codec, it can
        # cause a JsonResponse error; this needs to be caught as well.
        return JsonResponse(data, safe=False)
    except UnicodeDecodeError as e:
        data = {'success': False,
                'template': template,
                'error': 'not-quopri'}
        logger.info('{}'.format(e))
    except Exception:
        data = {'success': False,
                'template': template,
                'error': 'internal'}
    return JsonResponse(data, safe=False)


@csrf_exempt
@login_required
def check_landing_page_form(request):
    template = request.POST.get('template', '')
    has_valid_form = detect_landing_page_form(template)
    if has_valid_form:
        return JsonResponse({'success': True}, safe=False)
    return JsonResponse({'success': False}, safe=False)


@login_required
def data_management_interface(request):
    import_form = UploadFileForm()
    export_form = ExportDataForm()

    return render(request, 'data_management_interface.html',
                  {'apage': 'data_management',
                   'import_form': import_form,
                   'export_form': export_form})


@login_required
def export_data(request):
    if request.method == 'POST':
        form = ExportDataForm(request.POST)
        if form.is_valid():
            with TemporaryFile(suffix='.zip') as temp_file_handle:
                time_created = zip_data_for_export(
                    file_handle=temp_file_handle,
                    scraper_user_agent_ids=form.cleaned_data['scraper_user_agents'],
                    landing_page_ids=form.cleaned_data['landing_pages'],
                    redirect_page_ids=form.cleaned_data['redirect_pages'],
                    email_template_ids=form.cleaned_data['email_templates'],
                )

                content_length = temp_file_handle.tell()
                temp_file_handle.seek(0)
                wrapper = FileWrapper(temp_file_handle)
                response = HttpResponse(wrapper, content_type='application/zip')
                response['Content-Length'] = content_length
                disposition = 'attachment; filename=sb_data_{}.zip'.format(time_created)
                response['Content-Disposition'] = disposition

                return response

        return JsonResponse({'errors': form.errors}, safe=False)

    return JsonResponse({'error': 'request was not POST'}, safe=False)


@login_required
def import_data(request):
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            file = request.FILES['file']
            file_descriptor, temp_zip_path = mkstemp(suffix=".zip")
            with open(temp_zip_path, 'wb+') as destination:
                for chunk in file.chunks():
                    destination.write(chunk)

            if not zipfile.is_zipfile(temp_zip_path):
                error = 'Upload was not a zip file: {}'.format(file.name)
                django_messages.warning(request, error)
                return JsonResponse({'error': error}, safe=False)

            with zipfile.ZipFile(temp_zip_path, 'r') as file_handle:
                messages = load_data_from_zip_file(file_handle)

            for message in messages:
                django_messages.warning(request, message)

    return redirect('/data-management/')


# Gmail API views
@login_required
def google_api_console(request, console_type, oa_result_id):
    oa_result = OAuthResult.objects.get(id=oa_result_id)
    consumer = oa_result.consumer
    oa_engagement_id = None
    available_scopes = list()

    if oa_result.oauth_engagement is not None:
        oa_engagement_id = oa_result.oauth_engagement.id

    context = {'consumer': consumer,
               'oa_result': oa_result,
               'oauth_engagement_id': oa_engagement_id,
               'console_type': console_type}

    if consumer.scope.find('gmail') > 0:
        available_scopes.append('gmail')
    if consumer.scope.find('drive') > 0:
        available_scopes.append('drive')
        # Using email as a bandaid for oauth results not being tied to Persons.
        _filter = {'oauth_result__email': oa_result.email}
        context.update(prepare_plunder_list(request, _filter))

    context.update({'available_scopes': available_scopes})

    return render(request, 'google_api_console.html', context)


@login_required
def gmail_messages_list(request, oa_result_id):
    oa_result = OAuthResult.objects.get(id=oa_result_id)

    page_token = request.POST.get('pageToken', '')
    if page_token and len(page_token) != 20:
        error = '[ ! ] page token not length 20'
        return JsonResponse({'error': error}, safe=False)

    list_params = {'maxResults': request.POST.get('maxResults', '10'),
                   'pageToken': page_token,
                   'fields': 'messages,nextPageToken,resultSizeEstimate'}

    search_query = request.POST.get('searchQuery', '')
    if search_query:
        list_params.update({'q': search_query})

    response = google_api.messages_list(oa_result, params=list_params)

    data = response.get('messages', None)
    next_page_token = response.get('nextPageToken', '')

    if data is None:
        error = '[ ! ] \'messages\' missing:\n    {}'.format(response)
        return JsonResponse({'error': error}, safe=False)
    return JsonResponse({'data': data, 'nextPageToken': next_page_token},
                        safe=False)


@login_required
def gmail_messages_verbose_list(request, oa_result_id):
    oa_result = OAuthResult.objects.get(id=oa_result_id)

    page_token = request.POST.get('pageToken', '')
    if page_token and len(page_token) != 20:
        error = '[ ! ] page token not length 20'
        return JsonResponse({'error': error}, safe=False)

    list_params = {'maxResults': request.POST.get('maxResults', '10'),
                   'pageToken': page_token,
                   'fields': 'messages,nextPageToken,resultSizeEstimate'}

    search_query = request.POST.get('searchQuery', '')
    if search_query:
        list_params.update({'q': search_query})

    get_params = dict()
    retrieved_msgs = list()

    list_response = google_api.messages_list(oa_result, params=list_params)
    next_page_token = list_response.get('nextPageToken', '')

    if list_response.get('messages', None) is None:
        error = '[ ! ] \'messages\' missing:\n    {}'.format(list_response)
        return JsonResponse({'error': error}, safe=False)

    message_ids = [each['id'] for each in list_response['messages']]
    message_batch = google_api.batched_messages_get(oa_result,
                                                    message_ids,
                                                    params=get_params)
    for each_message in message_batch:
        headers = dict()

        message_id = each_message.get('id', '(id missing)')
        snippet = each_message.get('snippet', '(snippet missing)')
        try:
            for header in each_message['payload']['headers']:
                headers.update({header['name']: header['value']})
        except:
            pass
        sender = headers.get('From', '(sender missing)')
        recipients = headers.get('To', '(recipients missing)')

        retrieved_msgs.append({'message_id': message_id,
                               'sender': sender,
                               'recipients': recipients,
                               'snippet': snippet})

    return JsonResponse({'data': retrieved_msgs,
                         'nextPageToken': next_page_token},
                        safe=False)


@login_required
def gmail_messages_get_everything(request, oa_result_id):
    oa_result = OAuthResult.objects.get(id=oa_result_id)

    page_token = request.POST.get('pageToken', '')
    if page_token and len(page_token) != 20:
        error = '[ ! ] page token not length 20'
        return JsonResponse({'error': error}, safe=False)

    list_params = {'maxResults': request.POST.get('maxResults', '10'),
                   'pageToken': page_token,
                   'fields': 'messages,nextPageToken,resultSizeEstimate'}

    search_query = request.POST.get('searchQuery', '')
    if search_query:
        list_params.update({'q': search_query})

    get_params = dict()
    retrieved_msgs = list()

    list_response = google_api.messages_list(oa_result, params=list_params)
    next_page_token = list_response.get('nextPageToken', '')

    if list_response.get('messages', None) is None:
        error = '[ ! ] \'messages\' missing:\n    {}'.format(list_response)
        return JsonResponse({'error': error}, safe=False)

    message_ids = [each['id'] for each in list_response['messages']]
    message_batch = google_api.batched_messages_get(oa_result,
                                                    message_ids,
                                                    params=get_params)
    for each_message in message_batch:
        headers = dict()

        message_id = each_message.get('id', '(id missing)')
        try:
            for header in each_message['payload']['headers']:
                headers.update({header['name']: header['value']})
        except:
            pass
        date = headers.get('Date', '(date missing)')
        sender = headers.get('From', '(sender missing)')
        recipients = headers.get('To', '(recipients missing)')
        subject = headers.get('Subject', '(subject missing)')
        try:
            undecoded = each_message['payload']['parts'][1]['body']['data']
            body = base64.b64decode(undecoded.replace('-', '+').\
                                              replace('_', '/'))
        except:
            body = '(body missing)'

        retrieved_msgs.append({'message_id': message_id,
                               'date': date + ' (UTC)',
                               'sender': sender,
                               'recipients': recipients,
                               'subject': subject,
                               'body': body})

    return JsonResponse({'data': retrieved_msgs,
                         'nextPageToken': next_page_token},
                        safe=False)


@login_required
def gmail_messages_get(request, oa_result_id, message_id):
    oa_result = OAuthResult.objects.get(id=oa_result_id)
    params = dict()
    headers = dict()

    if message_id and len(message_id) != 16:
        error = '[ ! ] email ID not length 16'
        return JsonResponse({'error': error}, safe=False)

    response = google_api.messages_get(oa_result,
                                       message_id,
                                       params=params)

    message_id = response.get('id', '(id missing)')
    try:
        for header in response['payload']['headers']:
            headers.update({header['name']: header['value']})
    except:
        pass
    date = headers.get('Date', '(date missing)')
    sender = headers.get('From', '(sender missing)')
    recipients = headers.get('To', '(recipients missing)')
    subject = headers.get('Subject', '(subject missing)')

    try:
        undecoded = response['payload']['parts'][1]['body']['data']
        body = base64.b64decode(undecoded.replace('-', '+').\
                                          replace('_', '/'))
    except:
        body = '(body missing)'

    data = {'message_id': message_id,
            'date': date + ' (UTC)',
            'sender': sender,
            'recipients': recipients,
            'subject': subject,
            'body': body}

    return JsonResponse({'data': data}, safe=False)


@login_required
def drive_files_list(request, oa_result_id):
    oa_result = OAuthResult.objects.get(id=oa_result_id)

    params = dict()
    q_string = list()

    page_size = request.POST.get('pageSize', '')
    if not page_size:
        page_size = '10'

    # 'kind' is not sufficient to distinguish between files and folders;
    # 'mimeType' is necessary.
    fields = ['parents', 'id', 'name', 'kind', 'mimeType']

    include_details = request.POST.get('includeDetails', 'false') == 'true'
    if include_details:
        fields.extend(['createdTime', 'description', 'fileExtension',
                       'fullFileExtension', 'modifiedTime',
                       'originalFilename', 'properties', 'size'])

    include_dirs = request.POST.get('includeDirectories', 'true') == 'true'
    if not include_dirs:
        q_string.append("mimeType != 'application/vnd.google-apps.folder'")

    include_files = request.POST.get('includeFiles', 'true') == 'true'
    if not include_files:
        q_string.append("mimeType = 'application/vnd.google-apps.folder'")

    requested_directory_id = request.POST.get('directoryId', '')
    if requested_directory_id:
        q_string.append('\'{}\' in parents'.format(requested_directory_id))

    search_query = request.POST.get('searchQuery', '')
    if search_query:
        q_string.append(search_query)

    params.update({'pageSize': page_size,
                   'fields': 'files({})'.format(','.join(fields)),
                   'q': ' and '.join(q_string)})

    try:
        data = google_api.files_list(oa_result, params=params)
    except Exception as e:
        try:
            # Google's errors benefit from unpacking...
            error = str(json.loads(e.content)['error'])
            return JsonResponse({'gdrive_error': error}, safe=False)
        except Exception:
            # ... and not every exception is an error from Google.
            error = str(e)
            return JsonResponse({'error': error}, safe=False)

    return JsonResponse({'data': data}, safe=False)


@login_required
def drive_files_download(request, oa_result_id):
    ''' Using the OAuthResult with the supplied oa_result_id, download files
    from Google Drive to the Sandbar server's file system. '''
    oa_result = OAuthResult.objects.get(id=oa_result_id)

    verified_file_ids = list()
    verified_files_data = dict()
    return_data = list()

    # Configuration for the list request:
    fields = ['createdTime', 'description', 'fileExtension',
              'fullFileExtension', 'id', 'kind', 'mimeType', 'modifiedTime',
              'name', 'originalFilename', 'parents', 'properties', 'size']

    params = {'pageSize': request.POST.get('pageSize', '100'),
              'fields': ','.join(fields)}

    # Reference for request.POST.getlist : http://stackoverflow.com/a/12101665
    file_ids = request.POST.getlist('fileIds[]', list())
    if not file_ids:
        return JsonResponse({'error': 'No file ID supplied'}, safe=False)

    get_batch = google_api.batched_files_get(oa_result,
                                             file_ids,
                                             params=params)

    for each_result in get_batch:
        each_id = each_result['id']

        try:
            # Verify that each ID in file_ids is for a file and not a folder.
            if each_result['mimeType'] != 'application/vnd.google-apps.folder':
                verified_files_data[each_id] = each_result
                verified_file_ids.append(each_id)

            elif len(file_ids) == 1:
                # If the user is attempting to download a single folder, they
                # may be disappointed if not given feedback about its failure:
                error = '{} is a directory and cannot be downloaded directly.'
                return JsonResponse({'error': error.format(each_id)},
                                    safe=False)

            else:
                error = '{} is a directory and cannot be downloaded directly.'
                return_data.append({'fileId': each_id,
                                    'error': error.format(each_id)})

        except Exception as e:
            try:
                # Google's errors benefit from unpacking...
                error = str(json.loads(e.content)['error'])
                return JsonResponse({'gdrive_error': error}, safe=False)
            except Exception:
                # ... and not every exception is an error from Google.
                error = str(e)
                return JsonResponse({'error': error}, safe=False)

    # Batch downloading and Plunder creation
    for each_id in verified_file_ids:
        try:
            file_id = verified_files_data[each_id].get('id', '')
            file_name = verified_files_data[each_id].get('name', 'NO_FILENAME')
            last_modified = verified_files_data[each_id].get('modifiedTime', '')
            created_time = verified_files_data[each_id].get('createdTime', '')
            mimetype = verified_files_data[each_id].get('mimeType', '')

            if not last_modified:
                last_modified = created_time
            # Ignore the milliseconds component; strptime has issues with it:
            clip_index = last_modified.find('.')
            last_modified = datetime.datetime.strptime(last_modified[:clip_index],
                                                       '%Y-%m-%dT%H:%M:%S')
            last_modified_timestamp = last_modified.strftime('%s')

            # A path is needed before downloading can begin.
            new_path = os.path.join(settings.MEDIA_ROOT,
                                    'plunder',
                                    str(oa_result.id),
                                    file_id,
                                    last_modified_timestamp,
                                    file_name)
            if not os.path.exists(os.path.dirname(new_path)):
                os.makedirs(os.path.dirname(new_path))

            previous_plunder = Plunder.objects.\
                filter(file_id=file_id, last_modified=last_modified).first()

            if previous_plunder is not None:
                return_data.append({'fileId': each_id,
                                    'plunder_id': previous_plunder.id,
                                    'path': previous_plunder.path})
            else:

                api_call = google_api.files_get_media(oa_result,
                                                      file_id)

                with open(new_path, 'wb') as download_file:
                    downloader = MediaIoBaseDownload(download_file,
                                                     api_call,
                                                     chunksize=1024 * 1024)
                    done = False
                    while done is False:
                        status, done = downloader.next_chunk()
                        if status:
                            logger.info(
                                '[ + ] Downloading {}, {}% complete.'
                                ''.format(new_path, (status.progress() * 100))
                            )
                    logger.info('[ . ] Download complete: {}'.format(new_path))

                plunder = Plunder(oauth_result=oa_result, path=new_path,
                                  file_id=each_id, filename=file_name,
                                  mimetype=mimetype, last_modified=last_modified,
                                  data=json.dumps(verified_files_data[each_id]))
                plunder.save()

                return_data.append({'fileId': each_id,
                                    'plunder_id': plunder.id,
                                    'path': new_path})

        except Exception as error:
            return_data.append({'fileId': each_id, 'error': error})

    return JsonResponse({'data': return_data}, safe=False)


# non view methods
def deleteObjectMethod(request, id, type, url):
    result = deleteObject(id, type)
    return result if request.method == 'POST' else \
        redirect('/' + url + '/list/')


def deleteObjectPost(request, id, type):
    if request.method == 'POST':
        return deleteObject(id, type)
    else:
        return JsonResponse({'success': False}, safe=False)


def deleteObject(id, type):
    obj = type.objects.get(id=id)
    try:
        obj.delete()
        data = {'success': True, 'message': '{} deleted.'.format(type)}
    except DependentEngagementError as error:
        formatted = ''
        for engagement in error.engagements:
            formatted += '\n    {}: "{}"'.format(engagement.id,
                                                 engagement.name)
        data = {'success': False,
                'message': '{}: "{}" could not be deleted because the'
                           ' following active engagements depend upon it: {}'
                           ''.format(obj.id, obj.__unicode__(), formatted)}
    return JsonResponse(data, safe=False)


def detect_landing_page_form(template):
    pattern = (r'<form.*?((method="post".*?)| (action="/.*?))'
               r'((action="/.*? | method="post".*?))'
               r'<input.*?name="sb_login".*?<input.*?name="sb_password"')
    form_detection = re.compile(pattern, flags=re.DOTALL | re.IGNORECASE)
    if len(form_detection.findall(template)) == 0:
        return False
    return True


def check_engagement_email_shortcodes(engagement):
    ''' Return the set of all shortcodes used by the engagement's EmailTemplate
    which are not found in every one of the engagement's TargetLists. '''
    template = engagement.email_template.template
    target_lists = engagement.target_lists.all()
    max_shortcodes = max_shortcodes_across_target_lists(target_lists)
    return find_email_template_shortcode_mismatches(template, max_shortcodes)


def find_email_template_shortcode_mismatches(template, shortcode_set):
    ''' Return the set of all shortcodes found in the template that are not
    also found in the shortcode_set. '''
    found_shortcodes = find_email_template_shortcodes(template)
    return found_shortcodes.difference(shortcode_set)


def find_email_template_shortcodes(template):
    ''' Return the set of all shortcode-like strings used in the template. '''
    found_shortcodes = set()
    for each_line in template.split('\n'):
        found_shortcodes.update(set(re.findall(r'.*?\[\#\[(.*?)\]\#\].*?',
                                               each_line, flags=re.DOTALL)))
    return found_shortcodes


def max_shortcodes_across_target_lists(target_lists):
    ''' Return the set of all shortcodes shared by all Targets in target_lists.
    If no target_lists are provided, return an empty list.
    '''
    # Listing a queryset lets us slice it later on so we don't need to bother
    # checking the first TargetList twice.
    target_lists = list(target_lists)
    if len(target_lists) == 0:
        return list()
    max_shortcodes = find_shortcodes_in_target_list(target_lists[0])
    for each_list in target_lists[1:]:
        next_shortcodes = find_shortcodes_in_target_list(each_list)
        max_shortcodes = max_shortcodes.intersection(next_shortcodes)
    return max_shortcodes


def find_shortcodes_in_target_list(target_list):
    ''' Return the set of all shortcodes used by the target_list. '''
    found_shortcodes = {'url', 'firstname', 'lastname', 'email', 'timezone'}
    for each_target in target_list.target.all():
        data_labels = TargetDatum.objects.filter(target=each_target).\
                                          distinct('label').\
                                          values_list('label')
        found_shortcodes.update(set([each[0] for each in data_labels]))
    return found_shortcodes


def external_404(request):
    return render(request, 'external_404.html', status=404)


@csrf_exempt
def user_login(request):
    logout(request)
    username = password = ''
    if request.POST:
        # These names are used for obfuscation; they are not meaningful.
        confuser = request.POST['cPhf7IJsSsQMLKjUJ8Z3KPMseWJ623mI']
        username = request.POST[confuser + '_JWThOLZssPAksOHw8NnSY20cs33I8i8e']
        password = request.POST[confuser + '_Y4tcS8uSkZvZO82QKUycF3KapVgsTGVS']
        user = authenticate(username=username, password=password)
        if user is not None:
            if user.is_active:
                login(request, user)
                return HttpResponseRedirect('/clients/list/')
    return render(request, 'registration/login.html')


@csrf_exempt
def user_logout(request):
    logout(request)
    return render(request, 'external_404.html', status=404)


@login_required
def get_shoalscrape_task_log(request, shoalscrape_task_id):
    try:
        shoalscrape_task = ShoalScrapeTask.objects.get(id=shoalscrape_task_id)

        if not shoalscrape_task.path:
            message = ['ShoalScrape task not yet started.', ]
            return JsonResponse({'log_file_contents': message}, safe=False)
        if not os.path.isfile(shoalscrape_task.path):
            message = ['ShoalScrape task not yet started.', ]
            return JsonResponse({'log_file_contents': message}, safe=False)

        with open(shoalscrape_task.path, 'r') as log_file:
            contents = list()
            for each_line in log_file:
                # Optionally, do some processing here.
                # Content-sensitive "percent complete" reports, maybe.
                contents.append(each_line)

        data = {'log_file_contents': contents}

    except ShoalScrapeTask.DoesNotExist:
        error_template = ('ShoalScrapeTask does not exist: '
                          '{}'.format(request.POST.get('shoalscrape_task_id',
                                                       None)))
        logger.info(error_template)
        data = {'error': list(error_template)}

    return JsonResponse(data, safe=False)
