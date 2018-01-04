# -*- coding: utf-8 -*-
import re
import ssl
import cookielib
import logging
from sandbar import settings
from urllib2 import (Request, URLError, build_opener, HTTPCookieProcessor,
                     urlopen)

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.contrib.auth.models import User

from models import (Engagement, Target, Campaign, EmailServer, EmailTemplate,
                    LandingPage, TargetList, Client, Schedule,
                    ScraperUserAgent, OpenRedirect, PhishingDomain,
                    OAuthConsumer, OAuthEngagement, OAuthResult,
                    ShoalScrapeCreds)
from helpers import get_engagement_by_url

logger = logging.getLogger(__name__)


class ExportDataForm(forms.Form):
    scraper_user_agents = forms.ModelMultipleChoiceField(
        widget=forms.CheckboxSelectMultiple,
        queryset=ScraperUserAgent.objects.order_by('-id'),
        required=False)
    landing_pages = forms.ModelMultipleChoiceField(
        widget=forms.CheckboxSelectMultiple,
        queryset=LandingPage.objects.filter(is_redirect_page=False).\
                                     order_by('-id'),
        required=False)
    redirect_pages = forms.ModelMultipleChoiceField(
        widget=forms.CheckboxSelectMultiple,
        queryset=LandingPage.objects.filter(is_redirect_page=True).\
                                     order_by('-id'),
        required=False)
    email_templates = forms.ModelMultipleChoiceField(
        widget=forms.CheckboxSelectMultiple,
        queryset=EmailTemplate.objects.order_by('-id'),
        required=False)


class UploadFileForm(forms.Form):
    file = forms.FileField()


class EngagementForm(forms.Form):
    engagement_id = forms.IntegerField(widget=forms.HiddenInput(),
                                       required=False)
    campaign = forms.ModelChoiceField(queryset=Campaign.objects.\
                                                        order_by('-id'),
                                      required=True)
    name = forms.CharField(widget=forms.TextInput(), max_length=100,
                           required=True, label='Title')
    description = forms.CharField(widget=forms.Textarea, required=False)
    open_redirect = forms.ModelChoiceField(
        queryset=OpenRedirect.objects.order_by('-id'),
        required=False,
        label='Open Redirect',
        help_text='Pick an open redirect to use (optional)')
    domain = forms.ModelChoiceField(
        queryset=PhishingDomain.objects.order_by('-id'),
        required=True)
    path = forms.CharField(widget=forms.TextInput(attrs={'pattern':
                                              '^[\-\_\.\:\/\?\=&A-Za-z0-9]+$'}),
                           max_length=500,
                           required=False,
                           label='Landing Page URL',
                           help_text=('The URL may contain numbers, letters,'
                                      ' ".", ":", "_", "/", "&", "?", "=" and'
                                      ' "-". The URL may not contain the '
                                      'reserved string "/1x1".'))
    schedule = forms.ModelChoiceField(
        queryset=Schedule.objects.order_by('-id'),
        label="Schedule",
        required=True)
    email_server = forms.ModelChoiceField(
        queryset=EmailServer.objects.order_by('-id'),
        label="Send Using",
        required=True)
    email_template = forms.ModelChoiceField(
        queryset=EmailTemplate.objects.order_by('-id'),
        required=True)
    landing_page = forms.ModelChoiceField(
        queryset=LandingPage.objects.filter(is_redirect_page=False).\
                                     order_by('-id'),
        required=True)
    redirect_page = forms.ModelChoiceField(
        queryset=LandingPage.objects.filter(is_redirect_page=True).\
                                     order_by('-id'),
        required=True)
    target_lists = forms.ModelMultipleChoiceField(
        widget=forms.CheckboxSelectMultiple,
        queryset=TargetList.objects.order_by('-id'),
        required=True)
    start_type = forms.ChoiceField(
        choices=((u'immediately', u'Immediately'),
               (u'countdown', u'After an amount of time'),
               (u'specific_date', u'At a specific date and time')),
        required=True,
        label='Start type',
        widget=forms.RadioSelect(),
        initial='immediately'
    )
    start_date = forms.CharField(
        widget=forms.TextInput(),
        required=False,
        label='Start date'
    )
    start_time = forms.CharField(
        widget=forms.TextInput(),
        required=False,
        label='Start time'
    )

    def __init__(self, *args, **kwargs):
        super(EngagementForm, self).__init__(*args, **kwargs)
        landing_page = None
        initial = kwargs.get('initial')
        if initial:
            landing_page = initial.get('landing_page')
            engagement_id = initial.get('engagement_id')
            start_date = initial.get('start_date')
            start_time = initial.get('start_time')
            if start_date:
                start_date = start_date.strftime('%Y-%m-%d')
                kwargs['initial'].update(start_date=start_date)
            if start_time:
                start_time = start_time.strftime('%H:%M:%S')
                kwargs['initial'].update(start_time=start_time)
        if landing_page:
            self.fields['path'].help_text += (' View an internally-accessible'
                ' preview of this landing page at <a target="_blank" href="'
                'https://{host}/landing-pages/preview/{landing_page}/'
                '{engagement_id}/">https://{host}/landing-pages/preview/'
                '{landing_page}/{engagement_id}/</a>'
                ''.format(host=settings.HOST,
                          engagement_id=engagement_id,
                          landing_page=landing_page.id))

    def clean(self):
        engagement_id = self.cleaned_data['engagement_id']
        domain = self.cleaned_data.get('domain', '')
        path = self.cleaned_data.get('path', '')
        start_type = self.cleaned_data.get('start_type', 'immediate')
        start_date = self.cleaned_data.get('start_date', '')
        start_time = self.cleaned_data.get('start_time', '')

        try:
            url = '{}/{}'.format(domain.domain_name, path)
            engagement = get_engagement_by_url(url, remove_referral_id=False)
            if engagement is None:
                pass
            elif engagement.id != engagement_id:
                self.add_error('path', ValidationError('URL must be unique'
                                                       ' among all existing'
                                                       ' Engagements.'))
        except Engagement.MultipleObjectsReturned:
            logger.info('Multiple Engagements sharing one URL: %s' % url)
            self.add_error('path', ValidationError('More than one Engagement'
                                                   ' with this URL currently'
                                                   ' exists. Each URL must'
                                                   ' lead to only one'
                                                   ' Engagement.'))
        except AttributeError:
            # If the domain is missing, it will already be marked as required.
            pass
        except Engagement.DoesNotExist:
            # This means a new Engagement is being made.
            pass

        if re.match(r'.*(\/1x1).*', path):
            self.add_error('path', ValidationError('The character string '
                                                   '"/1x1" is reserved and may'
                                                   ' not be used in Engagement'
                                                   ' URLs.'))
        if path and not re.match(r'^[\-\_\.\:\/\?\=A-Za-z0-9]+$', path):
            self.add_error('path', ValidationError('The Engagement URL should'
                                                   ' contain numbers, letters,'
                                                   ' ".", ":", "_", "/", "?",'
                                                   ' "=" and "-" only.'))

        if start_type == 'immediate':
            if start_date:
                self.add_error('start_date', ValidationError('Engagements scheduled to send immediately may not have a start_date.'))
            if start_time:
                self.add_error('start_time', ValidationError('Engagements scheduled to send immediately may not have a start_time.'))
        elif start_type == 'countdown':
            if start_date:
                self.add_error('start_date', ValidationError('Engagements scheduled to send immediately may not have a start_date.'))
            if not start_time:
                self.add_error('start_time', ValidationError('Engagements scheduled to send immediately must have a start_time.'))
        elif start_type == 'specific_date':
            if not start_date:
                self.add_error('start_date', ValidationError('Engagements scheduled to send immediately must have a start_date.'))
            if not start_time:
                self.add_error('start_time', ValidationError('Engagements scheduled to send immediately must have a start_time.'))

        return self.cleaned_data


class OAuthEngagementForm(EngagementForm):
    open_redirect = None
    domain = None
    path = None
    landing_page = None
    redirect_page = None
    oauth_consumer = forms.ModelChoiceField(queryset=OAuthConsumer.objects.\
                                                               order_by('-id'),
                                            required=True)


class OAuthConsumerForm(forms.Form):
    oac_id = forms.IntegerField(widget=forms.HiddenInput(), required=False)
    name = forms.CharField(max_length=256, required=True)
    description = forms.CharField(widget=forms.Textarea, required=False)
    client_id = forms.CharField(max_length=256, required=True)
    client_secret = forms.CharField(max_length=256, required=True)
    scope = forms.CharField(max_length=256, required=True)
    callback_url = forms.CharField(max_length=256, required=True)
    bounce_url = forms.CharField(max_length=256, required=True)


class OAuthResultForm(forms.Form):
    oar_id = forms.IntegerField(widget=forms.HiddenInput(), required=False)
    email = forms.CharField(max_length=255, required=True)
    target = forms.ModelChoiceField(queryset=Target.objects.order_by('-id'),
                                    required=False)
    oauth_engagement = forms.ModelChoiceField(queryset=OAuthEngagement.\
                                                       objects.order_by('-id'),
                                              required=False)
    consumer = forms.ModelChoiceField(queryset=OAuthConsumer.\
                                                       objects.order_by('-id'),
                                      required=False)
    ip = forms.GenericIPAddressField(required=False)
    timestamp = forms.DateTimeField(required=False)
    userAgent = forms.CharField(max_length=255, required=False)


class PlunderForm(forms.Form):
    plunder_id = forms.IntegerField(widget=forms.HiddenInput(), required=False)
    oauth_result = forms.ModelChoiceField(queryset=OAuthResult.\
                                                       objects.order_by('-id'),
                                          required=False)
    path = forms.CharField(max_length=255, required=False)
    file_id = forms.CharField(max_length=255, required=False)
    filename = forms.CharField(max_length=255, required=False)
    mimetype = forms.CharField(max_length=255, required=False)
    last_modified = forms.DateTimeField(required=False)
    data = forms.CharField(widget=forms.Textarea, required=False)


class ClientForm(forms.Form):
    name = forms.CharField(max_length=100, required=True)
    url = forms.URLField(max_length=100, required=True, label='URL')
    default_time_zone = forms.ChoiceField(choices=Client.tz_list,
                                          required=True, initial='Etc/GMT+7')


class CampaignForm(forms.Form):
    campaign_id = forms.IntegerField(widget=forms.HiddenInput(),
                                     required=False)
    name = forms.CharField(max_length=100, required=True, label='Title')
    description = forms.CharField(widget=forms.Textarea, required=False)
    client = forms.ModelChoiceField(queryset=Client.objects.order_by('-id'),
                                    required=False)

    def clean_client(self):
        campaign_id = self.cleaned_data.get('campaign_id')
        client = self.cleaned_data.get('client')
        if campaign_id:
            try:
                return Client.objects.get(campaign__id=campaign_id)
            except Client.DoesNotExist:
                raise ValidationError('Client does not exist.')
        else:
            if not client:
                raise ValidationError('This field is required.')
            else:
                return client


class OpenRedirectForm(forms.Form):
    or_id = forms.IntegerField(widget=forms.HiddenInput(), required=False)
    url = forms.CharField(max_length=500, required=True, label='URL', help_text='Test?')


class PhishingDomainForm(forms.Form):
    pd_id = forms.IntegerField(widget=forms.HiddenInput(), required=False)
    protocol = forms.ChoiceField(choices=PhishingDomain.PROTOCOLS,
                                 label='Protocol',
                                 widget=forms.RadioSelect(),
                                 initial='https')
    domain_name = forms.CharField(max_length=500, required=True)

    def clean_domain_name(self):
        domain_name = self.cleaned_data.get('domain_name')
        if domain_name.startswith('http://') or \
                domain_name.startswith('https://'):
            raise ValidationError('Domain name should not begin with'
                                  ' a protocol. ("http://")')
        return domain_name.rstrip('/')


class SiteSettingsForm(forms.Form):
    public_ip = forms.GenericIPAddressField(required=True)


class SlackHookForm(forms.Form):
    sh_id = forms.IntegerField(widget=forms.HiddenInput(), required=False)
    webhook_url = forms.CharField(required=True, label='Webhook URL')
    description = forms.CharField(widget=forms.Textarea, required=False,
                                  label='Description')


class EmailServerForm(forms.Form):
    es_id = forms.IntegerField(widget=forms.HiddenInput(),
                               required=False)
    host = forms.CharField(max_length=100, required=True)
    port = forms.IntegerField(required=True)
    use_tls = forms.BooleanField(required=False)
    login = forms.EmailField(max_length=100, required=True)
    email_pw = forms.CharField(max_length=100,
                               required=True,
                               label='Account Password')
    test_recipient = forms.EmailField(required=False,
                                      initial='info@rhinosecuritylabs.com',
                                      label='Test this configuration:')


class EmailTemplateForm(forms.Form):
    et_id = forms.IntegerField(widget=forms.HiddenInput(),
                               required=False)
    name = forms.CharField(max_length=100, required=True,
                           label='Template Name')
    description = forms.CharField(widget=forms.Textarea, required=False,
                                  label='Description')
    from_header = forms.CharField(max_length=100, required=True,
                                  label='From Header')
    subject_header = forms.CharField(max_length=100, required=True,
                                     label='Subject')
    template = forms.CharField(widget=forms.Textarea, required=False)


class ScraperUserAgentForm(forms.Form):
    sua_id = forms.IntegerField(widget=forms.HiddenInput(), required=False)
    name = forms.CharField(max_length=100, required=True)
    user_agent_data = forms.CharField(widget=forms.Textarea, required=False)


class LandingPageForm(forms.Form):
    landing_page_id = forms.IntegerField(widget=forms.HiddenInput(),
                                         required=False)
    description = forms.CharField(widget=forms.Textarea, required=False)
    is_redirect_page = forms.BooleanField(widget=forms.HiddenInput(),
                                          initial=False, required=False)
    page_type = forms.\
        CharField(widget=forms.Select(choices=(('page', 'Scraped Page'),
                                               ('manual', 'Manual'))),
                  required=False, initial='page', label='Type')
    scraper_user_agent = forms.\
        ModelChoiceField(queryset=ScraperUserAgent.objects.order_by('-id'),
                         required=False, label='Scraper User Agent',
                         help_text='If JavaScript is enabled at the target'
                         ' URL, it is possible for the target to determine'
                         ' the browser and version via feature detection.'
                         ' Presenting a user-agent string from a browser'
                         ' engine different from Sandbar\'s may cause'
                         ' page-rendering errors.')
    name = forms.CharField(max_length=100, required=True, label='Title')
    url = forms.URLField(max_length=1000, required=False, label='URL')

    def __init__(self, *args, **kwargs):
        super(LandingPageForm, self).__init__(*args, **kwargs)
        # Reference: http://stackoverflow.com/a/741297
        self.fields['scraper_user_agent'].empty_label = "None"
        self.fields['scraper_user_agent'].widget.choices = \
                                      self.fields['scraper_user_agent'].choices

    def clean(self):
        # Overwriting `clean` instead of `clean_foo` is the Django-recommended
        # way of ensuring cross-field validation dependencies resolve in a
        # specific order. Reference: http://stackoverflow.com/a/11143938
        url = self.cleaned_data.get('url', '')
        page_type = self.cleaned_data.get('page_type', '')
        scraper_user_agent = self.cleaned_data.get('scraper_user_agent', '')
        if not scraper_user_agent:
            headers = {}
        else:
            headers = {'User-Agent': scraper_user_agent.user_agent_data}
        if page_type == 'page':
            if not url:
                self.add_error('url', ValidationError('A URL is required for'
                                                      ' scraped landing'
                                                      ' pages.'))
            else:
                validate = URLValidator()
                cj = cookielib.CookieJar()
                opener = build_opener(HTTPCookieProcessor(cj))
                try:
                    validate(url)
                    request = Request(url, None, headers)
                    opener.open(request).read()
                except ValidationError:
                    self.add_error('url', ValidationError('Enter a valid'
                                                          ' URL.'))
                except URLError:
                    try:
                        context = ssl._create_unverified_context()
                        request = Request(url, None, headers)
                        urlopen(request, context=context).read()
                    except Exception as e:
                        self.add_error('url', ValidationError(e))
                except Exception as e:
                    self.add_error('url', ValidationError(e))
        return self.cleaned_data


class RedirectPageForm(LandingPageForm):
    is_redirect_page = forms.BooleanField(widget=forms.HiddenInput(),
                                          initial=True, required=False)
    page_type = forms.\
        CharField(widget=forms.Select(choices=(('url', 'URL'),
                                               ('page', 'Scraped Page'),
                                               ('manual', 'Manual'))),
                  required=False, initial='url', label='Type')
    scraper_user_agent = forms.\
        ModelChoiceField(queryset=ScraperUserAgent.objects.order_by('-id'),
                         required=False, label='Scraper User Agent',
                         help_text='If JavaScript is enabled at the target'
                         ' URL, it is possible for the target to determine'
                         ' the browser and version via feature detection.'
                         ' Presenting a user-agent string from a browser'
                         ' engine different from Sandbar\'s may cause'
                         ' page-rendering errors.')
    url = forms.URLField(max_length=1000, required=False, label='URL')

    def clean(self):
        # Overwriting `clean` instead of `clean_foo` is the Django-recommended
        # way of ensuring cross-field validation dependencies resolve in a
        # specific order. Reference: http://stackoverflow.com/a/11143938
        url = self.cleaned_data.get('url', '')
        page_type = self.cleaned_data.get('page_type', '')
        scraper_user_agent = self.cleaned_data.get('scraper_user_agent', '')
        if not scraper_user_agent:
            headers = {}
        else:
            headers = {'User-Agent': scraper_user_agent.user_agent_data}
        if page_type == 'page':
            if not url:
                self.add_error('url',
                               ValidationError('A URL is required for'
                                               ' scraped landing pages.'))
            else:
                validate = URLValidator()
                cj = cookielib.CookieJar()
                opener = build_opener(HTTPCookieProcessor(cj))
                try:
                    validate(url)
                    request = Request(url, None, headers)
                    opener.open(request).read()
                except ValidationError:
                    self.add_error('url', ValidationError('Enter a valid'
                                                          ' URL.'))
                except URLError:
                    try:
                        context = ssl._create_unverified_context()
                        request = Request(url, None, headers)
                        urlopen(request, context=context).read()
                    except Exception as e:
                        self.add_error('url', ValidationError(e))
                except Exception as e:
                    self.add_error('url', ValidationError(e))

        elif page_type == 'url':
            if not url:
                self.add_error('url',
                               ValidationError('A URL is required for'
                                               ' scraped landing pages.'))
            else:
                headers = {'User-Agent': 'Mozilla/5.0'}
                validate = URLValidator()
                cj = cookielib.CookieJar()
                opener = build_opener(HTTPCookieProcessor(cj))
                try:
                    validate(url)
                    request = Request(url, None, headers)
                    opener.open(request).read()
                except ValidationError:
                    self.add_error('url', ValidationError('Enter a valid'
                                                          ' URL.'))
                except URLError as e:
                    self.add_error('url', ValidationError(e))
        return self.cleaned_data


class ScheduleForm(forms.Form):
    schedule_id = forms.IntegerField(widget=forms.HiddenInput(),
                                     required=False)
    name = forms.CharField(max_length=255,
                           required=True)
    description = forms.CharField(widget=forms.Textarea,
                                  required=False)
    is_default = forms.BooleanField(required=True)
    interval = forms.CharField(label='Sending interval',
                               initial='00:00:10',
                               help_text='Time between the sending of emails',
                               required=True)
    excluded_dates = forms.CharField(label='Excluded dates',
                               initial='',
                               help_text='Use comma-separated MM/DD/YY dates',
                               required=False)


class UserEditForm(forms.Form):
    user_id = forms.IntegerField(widget=forms.HiddenInput(),
                                 required=False)
    login = forms.CharField(max_length=30, required=True)
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30, required=False)
    last_name = forms.CharField(max_length=30, required=False)
    password = forms.CharField(widget=forms.PasswordInput, required=False)
    password2 = forms.CharField(widget=forms.PasswordInput,
                                label='Password Confirm', required=False)

    def __init__(self, *args, **kwargs):
        super(UserEditForm, self).__init__(*args, **kwargs)

        if not args or (args and not args[0].get('user_id')):
            self.fields['password'].required = True
        if kwargs.get('initial'):
            self.fields['password2'].help_text = ('Please fill out the fields '
                                                  '\'Password\' and '
                                                  '\'Password2\' in order to '
                                                  'change your password.')

    def clean_password2(self):
        password = self.cleaned_data.get('password')
        password2 = self.cleaned_data.get('password2')
        if password and password != password2:
            raise ValidationError('The two password fields didn\'t match.')

        return password2

    def clean_login(self):
        login = self.cleaned_data['login']
        user_id = self.cleaned_data.get('user_id')
        try:
            user = User.objects.get(username=login)
            if user.id != user_id:
                raise ValidationError('Someone already has that login.')
        except User.DoesNotExist:
            pass
        return login


class ShoalScrapeCredsForm(forms.Form):
    shoalscrape_creds_id = forms.IntegerField(widget=forms.HiddenInput(),
                                              required=False)
    name = forms.CharField(max_length=255, required=True)
    username = forms.CharField(max_length=255, required=True)
    password = forms.CharField(max_length=255, required=True)
    qs = ScraperUserAgent.objects.order_by('-id')
    scraper_user_agent = forms.ModelChoiceField(queryset=qs, required=False,
                                                label='Scraper user-agent')


class ShoalScrapeTaskForm(forms.Form):
    shoalscrape_task_id = forms.IntegerField(widget=forms.HiddenInput(),
                                             required=False)
    qs = ShoalScrapeCreds.objects.order_by('-id')
    shoalscrape_creds = forms.ModelChoiceField(queryset=qs, required=True,
                                               label='Credentials')
    company = forms.CharField(max_length=255, required=True)
    domain = forms.CharField(max_length=255, required=True)
    company_linkedin_id = forms.CharField(max_length=255, required=True,
                                          label="Company LinkedIn ID")
    last_started_at = forms.DateTimeField(required=False)
    path = forms.CharField(max_length=255, required=False)
