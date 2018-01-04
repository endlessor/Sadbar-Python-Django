# -*- coding: utf-8 -*-
from django.db import models
from django.db.models import Q
from django.utils import timezone as dj_tz
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.postgres.fields import ArrayField
import datetime
from dateutil import rrule
import json
import pytz
import re
import os
import shutil
import logging
from oauth2client.contrib.django_util.models import CredentialsField
from celery.task.control import revoke
from djcelery.models import PeriodicTask, IntervalSchedule
from Crypto.Hash import MD5
from client.slack_api import send_slack_message
from client.utils import b64_encrypt, b64_decrypt

logger = logging.getLogger(__name__)


class DependentEngagementError(Exception):
    def __init__(self, engagements, *args, **kwargs):
        self.engagements = engagements
        super(DependentEngagementError, self).__init__(*args, **kwargs)


class SiteSettings(models.Model):
    # Reference: http://stackoverflow.com/a/2300493
    _singleton = models.BooleanField(default=True, editable=False, unique=True)

    # For PhishingDomain checks.
    public_ip = models.GenericIPAddressField(null=True, blank=True,
                                             default='127.0.0.1')

    def __unicode__(self):
        return 'public_ip: {}'.format(self.public_ip)

    @classmethod
    def load(cls):
        try:
            return cls.objects.get()
        except cls.DoesNotExist:
            return cls.objects.create()

    def delete(self, *args, **kwargs):
        pass


class SlackHook(models.Model):
    webhook_url = models.TextField(blank=True, default='')
    description = models.TextField(blank=True, default='')

    def __unicode__(self):
        return '#{}: {}'.format(self.id, self.webhook_url[:80])


class Profile(models.Model):
    tz_list = zip(pytz.all_timezones, pytz.all_timezones)
    user = models.OneToOneField(User)
    timezone = models.CharField(choices=tz_list, max_length=32)


class EmailServer(models.Model):
    host = models.CharField(max_length=100, null=True)
    port = models.IntegerField(null=True)
    use_tls = models.BooleanField(default=False)
    login = models.CharField(max_length=100, null=True)
    password = models.CharField(max_length=100, null=True)
    test_recipient = models.EmailField(null=True, blank=True,
                                       default='info@rhinosecuritylabs.com')

    def __unicode__(self):
        return '#{}: {}'.format(self.id, self.login)

    def delete(self, *args, **kwargs):
        engs = Engagement.objects.filter(state=Engagement.IN_PROGRESS,
                                         email_server=self).order_by('-id')
        if engs.exists():
            engagement_ids = [engagement.id for engagement in engs]
            raise DependentEngagementError(engagements=engagement_ids)
        else:
            return super(EmailServer, self).delete(*args, **kwargs)


class OpenRedirect(models.Model):
    url = models.CharField(max_length=500, null=True)

    def __unicode__(self):
        return '#{}: {}'.format(self.id, self.url)

    def delete(self, *args, **kwargs):
        engs = Engagement.objects.filter(state=Engagement.IN_PROGRESS,
                                         email_server=self).order_by('-id')
        if engs.exists():
            raise DependentEngagementError(engagements=engs)
        else:
            return super(OpenRedirect, self).delete(*args, **kwargs)


class PhishingDomain(models.Model):
    PROTOCOLS = (('http', 'http'),
                 ('https', 'https'))
    protocol = models.CharField(max_length=5, null=True, choices=PROTOCOLS)
    domain_name = models.CharField(max_length=500, null=True)

    def __unicode__(self):
        return '{}://{}'.format(self.protocol, self.domain_name)

    def delete(self, *args, **kwargs):
        engs = Engagement.objects.filter(state=Engagement.IN_PROGRESS,
                                         domain=self).order_by('-id')
        if engs.exists():
            engagement_ids = [engagement.id for engagement in engs]
            raise DependentEngagementError(engagements=engagement_ids)
        else:
            return super(PhishingDomain, self).delete(*args, **kwargs)


class ScraperUserAgent(models.Model):
    name = models.CharField(max_length=100, null=True)
    user_agent_data = models.CharField(max_length=512, null=True, default='')

    def __unicode__(self):
        return self.name


class Schedule(models.Model):
    name = models.CharField(max_length=255, null=True)
    description = models.TextField(blank=True, null=True)
    is_default = models.BooleanField(blank=True, default=True)
    interval = models.IntegerField(blank=True, default=10)
    excluded_dates = ArrayField(
        models.DateField(blank=True),
        blank=True,
        default=list
    )

    def __unicode__(self):
        if self.is_default:
            return '#{} (default): {}'.format(self.id, self.name)
        return '#{} (custom): {}'.format(self.id, self.name)

    def delete(self, *args, **kwargs):
        engs = Engagement.objects.filter(state=Engagement.IN_PROGRESS,
                                         schedule=self).order_by('-id')
        if engs.exists():
            engagement_ids = [engagement.id for engagement in engs]
            raise DependentEngagementError(engagements=engagement_ids)
        else:
            return super(Schedule, self).delete(*args, **kwargs)

    def calculate_sending_times(self, initial_datetime, number_to_schedule):
        server_timezone = dj_tz.get_default_timezone()

        # Reference: https://dateutil.readthedocs.io/en/stable/examples.html
        ruleset = rrule.rruleset()

        if not self.windows.all().exists():
            ruleset.rrule(
                rrule.rrule(
                    rrule.SECONDLY,
                    interval=self.interval,
                    dtstart=initial_datetime
                )
            )

        for window in self.windows.all():
            rules = window.generate_rrules_with_rollover_accounted_for(self.interval, initial_datetime)
            for each in rules:
                ruleset.rrule(each)

        # ruleset.exdate only works for single-instant datetimes.
        # ruleset.exrule is how to add whole-day exclusion rules to a rruleset.
        for each_date in self.excluded_dates:
            ruleset.exrule(
                rrule.rrule(
                    rrule.DAILY,
                    byhour=range(0, 24),
                    byminute=range(0, 60),
                    bysecond=range(0, 60),
                    dtstart=server_timezone.localize(
                        datetime.datetime(
                            year=each_date.year,
                            month=each_date.month,
                            day=each_date.day,
                            hour=0,
                            minute=0,
                            second=0
                        )
                    ),
                    until=server_timezone.localize(
                        datetime.datetime(
                            year=each_date.year,
                            month=each_date.month,
                            day=each_date.day,
                            hour=23,
                            minute=59,
                            second=59
                        )
                    )
                )
            )

        scheduled_times = ruleset[:number_to_schedule]
        return scheduled_times


class ScheduleWindow(models.Model):
    WEEKDAY_CHOICES = (('monday', 'Monday'),
                       ('tuesday', 'Tuesday'),
                       ('wednesday', 'Wednesday'),
                       ('thursday', 'Thursday'),
                       ('friday', 'Friday'),
                       ('saturday', 'Saturday'),
                       ('sunday', 'Sunday'))

    schedule = models.ForeignKey('Schedule',
                                 on_delete=models.CASCADE,
                                 related_name='windows')
    day_of_the_week = models.CharField(choices=WEEKDAY_CHOICES,
                                       max_length=9,
                                       null=True,
                                       blank=True,
                                       default='monday')
    open_time = models.TimeField(default='00:00:00')
    close_time = models.TimeField(default='23:59:59')

    def __unicode__(self):
        return '#{}, for {}'.format(self.id, self.schedule)

    def delete(self, *args, **kwargs):
        engs = Engagement.objects.filter(state=Engagement.IN_PROGRESS,
                                         schedule=self.schedule).\
                                  order_by('-id')
        if engs.exists():
            engagement_ids = [engagement.id for engagement in engs]
            raise DependentEngagementError(engagements=engagement_ids)
        else:
            return super(ScheduleWindow, self).delete(*args, **kwargs)

    def generate_rrules_with_rollover_accounted_for(self, interval, initial_datetime):
        WEEKDAY_MAP = {
            'monday': rrule.MO,
            'tuesday': rrule.TU,
            'wednesday': rrule.WE,
            'thursday': rrule.TH,
            'friday': rrule.FR,
            'saturday': rrule.SA,
            'sunday': rrule.SU
        }

        open_hour, open_minute = self.open_time.hour, self.open_time.minute
        close_hour, close_minute = self.close_time.hour, self.close_time.minute

        common_rrule_parameters = {
            'interval': interval,
            'dtstart': initial_datetime
        }

        if self.day_of_the_week:
            common_rrule_parameters.update({
                'byweekday': WEEKDAY_MAP[self.day_of_the_week]
            })

        # Return an iterable instead of an rruleset so it can be merged with
        # other rrulesets for other ScheduleWindows.
        rrules = list()

        # In this case, only one rrule is needed.
        if open_hour == close_hour:
            rrules.append(
                rrule.rrule(
                    rrule.SECONDLY,
                    byhour=[open_hour],
                    byminute=range(open_minute, close_minute + 1),
                    **common_rrule_parameters
                )
            )

        # In this case, at least two rrules are needed: "open" and "close."
        if close_hour - open_hour >= 1:
            # The open rule:
            rrules.append(
                rrule.rrule(
                    rrule.SECONDLY,
                    byhour=[open_hour],
                    byminute=range(open_minute, 60),
                    **common_rrule_parameters
               )
            )
            # The close rule:
            rrules.append(
                rrule.rrule(
                    rrule.SECONDLY,
                    byhour=[close_hour],
                    byminute=range(0, close_minute + 1),
                    **common_rrule_parameters
                )
            )

        # In this case, a third rrule is also needed, an "intermediate" rrule,
        # where every minute in the rule's hours is schedulable.
        if close_hour - open_hour >= 2:
            rrules.append(
                rrule.rrule(
                    rrule.SECONDLY,
                    byhour=range(open_hour + 1, close_hour),
                    byminute=range(0, 60),
                    **common_rrule_parameters
                )
            )

        return rrules


class LandingPage(models.Model):
    STATUSES = ((1, 'ok'),
                (2, 'refresh refresh-animate'),
                (3, 'remove'))
    PAGE_TYPES = (('url', 'URL'),
                  ('page', 'Scraped Page'),
                  ('manual', 'Manual'))
    name = models.CharField(max_length=100, null=True)
    description = models.TextField(blank=True, null=True)
    url = models.CharField(max_length=1000, null=True, blank=True)
    path = models.CharField(max_length=255, null=True, blank=True)
    is_redirect_page = models.BooleanField(default=False)
    status = models.SmallIntegerField(choices=STATUSES,
                                      default=2, null=True)
    page_type = models.CharField(choices=PAGE_TYPES,
                                 max_length=10, default='page')
    scraper_user_agent = models.ForeignKey('ScraperUserAgent',
                                           null=True, blank=True,
                                           on_delete=models.SET_NULL,
                                           related_name='landing_pages')
    date_created = models.DateTimeField(auto_now_add=True, null=True,
                                        blank=True)

    def __unicode__(self):
        return '#{}: {}'.format(self.id, self.name)

    def remove_files(self):
        """ Remove a LandingPage's path's parent directory and all files
        inside it. Return a description of the result of this operation. """

        html_file_path = os.path.relpath(self.path)
        html_directory = os.path.dirname(html_file_path)
        page_directory = os.path.dirname(html_directory)
        type_directory = os.path.split(os.path.dirname(page_directory))[-1]

        if type_directory not in ('landing-pages', 'redirect-pages'):
            message = '[ ! ] Incorrect path to delete: {}'
        elif os.path.isdir(page_directory):
            message = '[ - ] Deleted: {}'
            shutil.rmtree(page_directory)
        else:
            message = '[ ! ] Nonexistent directory: {}'

        return message

    def delete(self, *args, **kwargs):
        engs = Engagement.objects.filter(Q(state=Engagement.IN_PROGRESS,
                                           landing_page=self) |
                                         Q(state=Engagement.IN_PROGRESS,
                                           redirect_page=self)).order_by('-id')
        if engs.exists():
            engagement_ids = [engagement.id for engagement in engs]
            raise DependentEngagementError(engagements=engagement_ids)
            return

        result = super(LandingPage, self).delete(*args, **kwargs)

        try:
            message = self.remove_files()
        except (IndexError, ValueError):
            message = '[ ! ] Incorrect path to delete: {}'
        logging.info(message.format(self.path))

        return result


class EmailTemplate(models.Model):
    name = models.CharField(max_length=100, null=True)
    description = models.TextField(blank=True, null=True)
    from_header = models.CharField(max_length=100, null=True)
    subject_header = models.CharField(max_length=100, null=True)
    template = models.TextField(null=True)

    def __unicode__(self):
        return '#{}: {}'.format(self.id, self.name)

    def delete(self, *args, **kwargs):
        engs = Engagement.objects.filter(state=Engagement.IN_PROGRESS,
                                         email_template=self).order_by('-id')
        if engs.exists():
            engagement_ids = [engagement.id for engagement in engs]
            raise DependentEngagementError(engagements=engagement_ids)
        else:
            return super(EmailTemplate, self).delete(*args, **kwargs)


class Client(models.Model):
    INVALID_TIMEZONE = -1
    tz_list = zip(pytz.all_timezones, pytz.all_timezones)
    name = models.CharField(max_length=100, null=True)
    url = models.CharField(max_length=100, null=True)
    default_time_zone = models.CharField(choices=tz_list,
                                         max_length=32,
                                         null=True)

    def __unicode__(self):
        return self.name


class Campaign(models.Model):
    name = models.CharField(max_length=100, null=True)
    description = models.TextField(blank=True, null=True)
    client = models.ForeignKey(Client, null=True, on_delete=models.CASCADE)

    def __unicode__(self):
        return '#{}: {}'.format(self.id, self.name)

    @property
    def status(self):
        active_engs = Engagement.objects.\
            filter(campaign=self, state=Engagement.IN_PROGRESS)
        all_engs = Engagement.objects.\
            filter(campaign=self).all()

        return (active_engs.exists(),
                '{}/{}'.format(active_engs.count(), all_engs.count()))


class ResultEvent(models.Model):
    NOT_SENT = 0
    OPEN = 1
    CLICK = 2
    SUBMIT = 3
    CHOICES = ((NOT_SENT, 'Not sent'),
               (OPEN, 'Open'),
               (CLICK, 'Click'),
               (SUBMIT, 'Submit'),)
    event_type = models.IntegerField(choices=CHOICES, default=0)
    timestamp = models.DateTimeField(null=True)
    userAgent = models.CharField(max_length=255, null=True)
    ip = models.GenericIPAddressField(null=True)
    login = models.CharField(max_length=100, null=True)
    password = models.CharField(max_length=100, null=True)
    raw_data = models.TextField(null=True)


class TargetDatum(models.Model):
    target_list = models.ForeignKey('TargetList', null=True,
                                    on_delete=models.CASCADE)
    target = models.ForeignKey('Target', null=True, on_delete=models.CASCADE)
    label = models.CharField(max_length=100, null=True)
    value = models.TextField(null=True, blank=True)

    def __unicode__(self):
        return self.label


class Target(models.Model):
    tz_list = Client.tz_list
    email = models.EmailField(null=True)
    firstname = models.CharField(max_length=50, null=True, blank=True)
    lastname = models.CharField(max_length=50, null=True, blank=True)
    timezone = models.CharField(choices=tz_list, max_length=32,
                                null=True, blank=True)

    def __unicode__(self):
        return unicode(self.email)

    def save(self, *args, **kwargs):
        # This prevents invalid timezone inputs from being saved and clears
        # the Target's timezone when passed the '(use client)' option.
        try:
            pytz.timezone(self.timezone)
        except:
            self.timezone = None
        super(Target, self).save(*args, **kwargs)

    def encrypt_id(self, engagement_url_key):
        ''' Using the supplied `engagement_url_key`, return the encrypted value
        of this Target instance's `id` attribute, encoded to base 64. '''
        return b64_encrypt(engagement_url_key, str(self.id))

    @classmethod
    def decrypt_id(cls, engagement_url_key, ciphertext):
        ''' Using the supplied `engagement_url_key`, decode the supplied
        `ciphertext` from base 64, decrypt it, convert that to an int, and
        return the result. '''
        try:
            return int(b64_decrypt(engagement_url_key, str(ciphertext)))
        except (ValueError, TypeError):
            return None

    def get_timezone(self):
        # I chose not to make this a property so as to differentiate it from
        # the timezone attribute and force conscious use.
        # Falsiness permits both None and the empty string as "nullish" values;
        # simple support for csv_parser.js returning empty strings.
        if self.timezone:
            return self.timezone
        else:
            # Validation of Targets that relies upon gathering serializer data
            # while those Targets are not saved to a TargetList (such as when
            # the TargetList has just had all of its Targets cleared during an
            # update through the API and that change was not yet saved).
            target_list = self.targetlist_set.last()
            if target_list is None:
                return self.timezone
            if target_list.client is None:
                return self.timezone
            return target_list.client.default_time_zone


class TargetList(models.Model):
    nickname = models.CharField(max_length=100, null=True)
    description = models.CharField(max_length=100, null=True, blank=True)
    target = models.ManyToManyField(Target)
    client = models.ForeignKey(Client, null=True, on_delete=models.CASCADE)

    def __unicode__(self):
        return self.nickname


class VectorEmail(models.Model):
    ALL_STATES = (0, 1, 2, 3, 4, 5)
    UNSCHEDULED = 0
    READY = 1
    PAUSED = 2
    ERROR = 3
    SENT = 4
    SEND_MISSED = 5
    STATE_CHOICES = ((UNSCHEDULED, 'Unscheduled'),
                     (READY, 'Ready'),
                     (PAUSED, 'Paused'),
                     (ERROR, 'Error'),
                     (SENT, 'Sent'),
                     (SEND_MISSED, 'Send Missed'))

    custom_state = models.BooleanField(default=False)
    state = models.SmallIntegerField(choices=STATE_CHOICES,
                                     default=UNSCHEDULED)

    engagement = models.ForeignKey('Engagement',
                                   null=True,
                                   on_delete=models.CASCADE,
                                   related_name='vector_email')
    target = models.ForeignKey('Target',
                               null=True,
                               on_delete=models.CASCADE,
                               related_name='vector_email')
    result_event = models.ManyToManyField(ResultEvent,
                                          related_name='vector_email')

    periodic_task = models.ForeignKey(PeriodicTask, null=True)

    custom_email_template = models.BooleanField(default=False)
    email_template = models.ForeignKey(EmailTemplate,
                                       null=True,
                                       on_delete=models.SET_NULL,
                                       related_name='vector_email')
    custom_landing_page = models.BooleanField(default=False)
    landing_page = models.ForeignKey(LandingPage,
                                     null=True,
                                     on_delete=models.SET_NULL,
                                     related_name='landing_page_vector_email')
    custom_redirect_page = models.BooleanField(default=False)
    redirect_page = models.ForeignKey(LandingPage,
                                     null=True,
                                     on_delete=models.SET_NULL,
                                     related_name='redirect_page_vector_email')

    custom_send_at = models.BooleanField(default=False)
    send_at = models.DateTimeField(null=True)
    sent_timestamp = models.DateTimeField(null=True)
    error = models.TextField(null=True, blank=True, default='')

    def __unicode__(self):
        return 'VE {} (TID {})'.format(self.id, self.target.id)

    @property
    def send_at_passed(self):
        deadline = self.send_at + datetime.timedelta(seconds=60)
        if deadline < dj_tz.localtime(dj_tz.now()):
            return True
        else:
            return False

    @property
    def targeted_oauth_result(self):
        """ Return the last member of a queryset with all OAuthResults for this
        VectorEmail where:
        - each result's engagement is this VectorEmail's engagement
        - each result's target is this VectorEmail's target
        - each result's email is this VectorEmail's target's email
        - each result's consumer is this VectorEmail's engagement's consumer.
        """
        if not self.engagement.is_oauth:
            return None

        oauth_engagement = self.engagement.oauthengagement
        oauth_results = oauth_engagement.oauth_results
        consumer = oauth_engagement.oauth_consumer
        target = self.target
        email = target.email

        results_for_this_ve = oauth_results.filter(target=target,
                                                   email__iexact=email,
                                                   consumer=consumer)

        return results_for_this_ve.last()

    @property
    def error_details(self):
        code = None
        text = None
        suggestion = None

        try:
            error_dict = json.loads(self.error)
            suggestion = error_dict.get('suggestion', None)
        except:
            # If the JSON fails to load, the error is not interpretable.
            return None, None, None

        try:
            # Some error data requires an additional, internal json parse.
            all_raw_errors = json.loads(error_dict.get('error'))
            # If it exists, this should be a list: [smtp_error_code, text]
            code, text = all_raw_errors.get(self.target.email)
        except:
            # Permit suggestions to be returned when an error does not have an
            # SMTP error code, or is otherwise uninterpretable.
            pass

        return code, text, suggestion

    def set_state(self, new_state):
        """ Set the state of this VectorEmail to the new_state.
        Changing state to VectorEmail.READY will start the VectorEmail's
        email-sending task.
        Changing state to VectorEmail.PAUSED, VectorEmail.ERROR, or
        VectorEmail.SENT will stop the VectorEmail's email-sending task.
        Does not check this VectorEmail's custom_state. """

        self.state = new_state
        self.save()

        # Every VectorEmail.state that is not intended to start its email-
        # sending task should instead ensure that its task is stopped.
        if new_state in (VectorEmail.UNSCHEDULED,
                         VectorEmail.PAUSED,
                         VectorEmail.ERROR,
                         VectorEmail.SENT,
                         VectorEmail.SEND_MISSED):
            self.stop_email_sending_task()
        elif new_state == VectorEmail.READY:
            self.start_email_sending_task()

    def update_schedule(self, send_at):
        """ Update the VectorEmail's send_at attribute and PeriodicTask.
        Does not check this VectorEmail's custom_send_at. """

        self.send_at = send_at
        self.save()

        if self.periodic_task is not None:
            internal_interval = self.periodic_task.interval
            self.periodic_task.delete()
            internal_interval.delete()  # Clear up unused IntervalSchedules

        ptask_name = 'send_vemail__v{}__t{}__e{}'.format(self.id,
                                                         self.target.id,
                                                         self.engagement.id)

        internal_interval = IntervalSchedule(every=20, period='seconds')
        internal_interval.save()

        # Of the PeriodicTask run-state information, only `enabled` should be
        # set here, because the default is True and that causes the task to be
        # started before Sandbar toggles it on.
        ptask = PeriodicTask(
            name=ptask_name,
            task='client.tasks.send_single_html_mail',
            interval=internal_interval,
            enabled=False,
            args=[self.id],
            kwargs={}
        )
        ptask.save()
        self.periodic_task = ptask
        self.save()

    def stop_email_sending_task(self):
        """ Disable this VectorEmail's sending task.
        Does not affect this VectorEmail's state.
        Does not change this VectorEmail's send_at time. """

        ptask = self.periodic_task
        ptask.enabled = False
        ptask.description = 'Stopped'
        ptask.save()

    def start_email_sending_task(self):
        """ Enable this VectorEmail's sending task.
        Will set this VectorEmail to VectorEmail.SEND_MISSED if send_at_passed
        is True.
        Does not change this VectorEmail's send_at time. """

        if self.send_at_passed is True:
            self.set_state(VectorEmail.SEND_MISSED)
            return

        ptask = self.periodic_task
        ptask.description = 'Started'

        ptask.enabled = True
        ptask.save()
        ptask.last_run_at = self.send_at
        ptask.save()


class Engagement(models.Model):
    ALL_STATES = (0, 1, 2, 3, 4)
    NOT_LAUNCHED = 0
    IN_PROGRESS = 1
    PAUSED = 2
    ERROR = 3
    COMPLETE = 4
    STATE_CHOICES = ((NOT_LAUNCHED, 'Not Launched'),
                     (IN_PROGRESS, 'In Progress'),
                     (PAUSED, 'Paused'),
                     (ERROR, 'Error'),
                     (COMPLETE, 'Complete'),)

    START_TYPES = (('immediate', 'Immediate'),
                   ('countdown', 'Countdown'),
                   ('specific_date', 'Specific date'))

    name = models.CharField(max_length=100,
                            null=True)
    description = models.TextField(blank=True,
                                   null=True)
    open_redirect = models.ForeignKey(OpenRedirect,
                                      null=True,
                                      blank=True,
                                      on_delete=models.SET_NULL,
                                      related_name='engagement')
    domain = models.ForeignKey(PhishingDomain,
                               null=True,
                               on_delete=models.SET_NULL,
                               related_name='engagement')
    path = models.CharField(max_length=500,
                            null=True,
                            blank=True,
                            default='')
    schedule = models.ForeignKey(Schedule,
                                 null=True,
                                 on_delete=models.SET_NULL,
                                 related_name='engagement')
    email_server = models.ForeignKey(EmailServer,
                                     null=True,
                                     on_delete=models.SET_NULL,
                                     related_name='engagement')
    email_template = models.ForeignKey(EmailTemplate,
                                       null=True,
                                       on_delete=models.SET_NULL,
                                       related_name='engagement')
    landing_page = models.ForeignKey(LandingPage,
                                     null=True,
                                     on_delete=models.SET_NULL,
                                     related_name='landing_page_engagement')
    redirect_page = models.ForeignKey(LandingPage,
                                      null=True,
                                      on_delete=models.SET_NULL,
                                      related_name='redirect_page_engagement')
    target_lists = models.ManyToManyField(TargetList)
    campaign = models.ForeignKey(Campaign,
                                 null=True,
                                 on_delete=models.CASCADE)
    url_key = models.CharField(max_length=32,
                               null=True,
                               editable=False)
    state = models.SmallIntegerField(choices=STATE_CHOICES,
                                     editable=False,
                                     default=NOT_LAUNCHED)
    start_type = models.CharField(choices=START_TYPES,
                                  max_length=15,
                                  default='immediate')
    start_date = models.DateField(null=True,
                                  blank=True)
    start_time = models.TimeField(null=True,
                                  blank=True)
    internal_error = models.TextField(blank=True, default='')

    def __unicode__(self):
        return '#{}: {}'.format(self.id, self.name)

    @property
    def is_oauth(self):
        """ As a property, return whether or not this Engagement is an
        OAuthEngagement or the Engagement for an OAuthEngagement.
        Useful for template tags. """
        if type(self) == OAuthEngagement:
            return True
        try:
            self.oauthengagement
            return True
        except OAuthEngagement.DoesNotExist:
            return False

    @property
    def oauth_consumer(self):
        """
        As a property, attempt to return either this OAuthEngagement's
        oauth_consumer, or this Engagement's oauthengagement's oauth_consumer.
        If neither are found, return None.
        """
        if type(self) == OAuthEngagement:
            return self.oauth_consumer
        try:
            return self.oauthengagement.oauth_consumer
        except OAuthConsumer.DoesNotExist:
            return None
        except OAuthEngagement.DoesNotExist:
            return None

    @property
    def current_process_error(self):
        """
        Return a tuple containing two values:
            [0] a string containing this Engagement's SMTP error code, or None
            [1] a string containing this Engagement's full error text, or None
        """
        if self.state == Engagement.ERROR:
            vector_emails_with_errors = VectorEmail.objects.\
                filter(engagement=self, state=VectorEmail.ERROR)
            if vector_emails_with_errors:
                error_text = vector_emails_with_errors.last().error
            else:
                if len(self.missing_dependencies) > 0:
                    dependencies = ', '.join(self.missing_dependencies)
                    error_text = ('This engagement is missing the following'
                                  ' dependencies: {}'.format(dependencies))
                elif len(self.internal_error) > 0:
                    error_text = self.internal_error
                else:
                    error_text = ('Internal error (no missing engagement '
                                  'dependencies or SMTP error details found)')
            error_code = re.compile(r'\[(\d\d\d)\,').search(error_text)
            if error_code:
                error_code = error_code.group(1)
                return error_code, error_text
            return '*', error_text
        return None, None

    @property
    def status(self):
        """
        Return a tuple containing three values:
            [0] an integer representing the current state of this Engagement
            [1] a string composed of the ratio of sent VectorEmails in this
            Engagement to the total number of VectorEmails in this Engagement
            [2] the `current_process_error` of this Engagement
        """
        all_self_emails = VectorEmail.objects.filter(engagement=self)
        sent_emails = all_self_emails.filter(state=VectorEmail.SENT)
        return (self.state,
                '{}/{}'.format(sent_emails.count(), all_self_emails.count()),
                self.current_process_error)

    @property
    def url(self):
        if self.is_oauth:
            try:
                return self.oauthengagement.oauth_consumer.callback_url
            except:
                return self.oauth_consumer.callback_url
        return '{}/{}'.format(self.domain.domain_name, self.path)

    @property
    def missing_dependencies(self):
        """ Return a list of strings describing the Engagement's missing
        necessary dependencies. """
        missing_dependencies = []
        if self.schedule is None:
            missing_dependencies.append('schedule')
        if self.email_server is None:
            missing_dependencies.append('email_server')
        if self.email_template is None:
            missing_dependencies.append('email_template')
        if self.target_lists.exists() is False:
            missing_dependencies.append('target_lists')
        if self.is_oauth is True and \
                self.oauthengagement.oauth_consumer is None:
            missing_dependencies.append('oauth_consumer')
        if self.is_oauth is False and self.domain is None:
            missing_dependencies.append('domain')
        if self.is_oauth is False and self.landing_page is None:
            missing_dependencies.append('landing_page')
        if self.is_oauth is False and self.redirect_page is None:
            missing_dependencies.append('redirect_page')
        return missing_dependencies

    def generate_url_key(self):
        """ Return the 32 byte hex-encoded MD5 hash of the Engagement's id. """
        # MD5 is obscurity, not security. MD5 hashes to a 128 bit (16 byte)
        # string. Hex encoding doubles the length of it to 32 bytes.
        return MD5.new(str(self.id)).hexdigest()

    def set_state(self, new_state):
        """ Set the state of an Engagement.

        If the new_state is NOT_LAUNCHED, ERROR, PAUSED, or COMPLETE, call
        _pause_engagement on the Engagement.

        If the new state is IN_PROGRESS and the old state is NOT_LAUNCHED or
        COMPLETE, call _start_engagement(start_mode='start') on the Engagement.

        If the new state is IN_PROGRESS and the old state is PAUSED or ERROR,
        call _start_engagement(start_mode='unpause') on the Engagement. """

        self.state, old_state = new_state, self.state
        self.save()

        # This needs to come early in the process. Scheduling errors are
        # caught, so having this afterwards wipes their internal_errors.
        if new_state != Engagement.ERROR:
            self.internal_error = ''
            self.save()

        if new_state in (Engagement.NOT_LAUNCHED,
                         Engagement.ERROR,
                         Engagement.PAUSED,
                         Engagement.COMPLETE):
            self._pause_engagement()

        elif new_state == Engagement.IN_PROGRESS:
            if old_state in (Engagement.NOT_LAUNCHED, Engagement.COMPLETE):
                starting_message = self._start_engagement(start_mode='start')
            elif old_state in (Engagement.PAUSED, Engagement.ERROR):
                starting_message = self._start_engagement(start_mode='unpause')

            if starting_message != 'Success':
                error_message = '[ . ] Engagement #{} start aborted: {}'
                logger.info(error_message.format(self.id, starting_message))
                return

        try:
            if new_state == Engagement.IN_PROGRESS:
                slack_hook = SlackHook.objects.last()
                link = 'https://{}/engagements/edit/{}/'.format(settings.HOST,
                                                                self.id)
                text = '\n'.join([
                    '<!here> - *Engagement Started!*',
                    '```#####################',
                    str(self.campaign.client.name),
                    str(self.name),
                    str(link),
                    '#####################```'
                ])
                send_slack_message('#sandbar-alerts', 'Sandbar',
                                   ':fishing_pole_and_fish:', text, slack_hook)
            elif new_state == Engagement.ERROR:
                slack_hook = SlackHook.objects.last()
                link = 'https://{}/engagements/edit/{}/'.format(settings.HOST,
                                                                self.id)
                text = '\n'.join([
                    '<!here> - *Engagement Error!*',
                    '```#####################',
                    str(self.campaign.client.name),
                    str(self.name),
                    str(link),
                    '{}:\n{}'.format(*self.current_process_error),
                    '#####################```'
                ])
                send_slack_message('#sandbar-alerts', 'Sandbar',
                                   ':fishing_pole_and_fish:', text, slack_hook)
            elif new_state == Engagement.COMPLETE:
                slack_hook = SlackHook.objects.last()
                link = 'https://{}/engagements/edit/{}/'.format(settings.HOST,
                                                                self.id)
                text = '\n'.join([
                    '*Engagement Complete*',
                    '```#####################',
                    str(self.campaign.client.name),
                    str(self.name),
                    str(link),
                    '#####################```'
                ])
                send_slack_message('#sandbar-alerts', 'Sandbar',
                                   ':fishing_pole_and_fish:', text, slack_hook)
        except Exception as e:
            message = '[ ! ] Error attempting to send Slack message: {}'
            logger.warn(message.format(e))

    def _start_engagement(self, start_mode):
        """ Attempt to begin the sending of all VectorEmails in an Engagement.
        Engagements with missing dependencies will be set to the ERROR state.

        If start_mode is 'start', all VectorEmails associated with this
        Engagement that are not in the READY state and do not have the
        custom_state flag set will have their sending scheduled and their
        current sent_timestamp, if any, set to None.

        If start_mode is 'unpause', it will work as above except VectorEmails
        in the SENT state will be ignored, and no VectorEmails will have their
        sent_timestamp set to None. """

        # This prevents the Engagement from entering any unpaused state while
        # all of its VectorEmails are marked as SENT without resetting their
        # states (which meant there was no way to restart the Engagement
        # because it would only toggle between paused and ready while leaving
        # all of its VectorEmails marked as SENT):
        if start_mode == 'unpause' and \
                VectorEmail.objects.filter(engagement=self).\
                                    exclude(state__in=[VectorEmail.SENT]).\
                                    exists() is False:
            self.set_state(Engagement.COMPLETE)
            return 'Completed'

        if len(self.missing_dependencies) > 0:
            self.set_state(Engagement.ERROR)
            return 'Missing dependencies'

        states_to_reschedule = tuple()
        if start_mode == 'start':
            states_to_reschedule = (VectorEmail.UNSCHEDULED,
                                    VectorEmail.PAUSED,
                                    VectorEmail.ERROR,
                                    VectorEmail.SENT,
                                    VectorEmail.SEND_MISSED)
        if start_mode == 'unpause':
            states_to_reschedule = (VectorEmail.UNSCHEDULED,
                                    VectorEmail.PAUSED,
                                    VectorEmail.ERROR,
                                    VectorEmail.SEND_MISSED)

        try:
            self.schedule_vector_emails(states_to_reschedule=states_to_reschedule)
        except Exception as error:
            logger.info('[ ! ] Exception in Engagement #{}'
                        ' schedule_vector_emails: {}'.format(self.id, error))
            self.internal_error = '{}: {}'.format(str(type(error)), str(error))
            self.save()
            self.set_state(Engagement.ERROR)
            return 'Scheduling failure'

        vector_emails_to_reschedule = VectorEmail.objects.filter(
            engagement=self,
            custom_state=False,
            state__in=states_to_reschedule
        )

        for vector_email in vector_emails_to_reschedule:
            if start_mode == 'start':
                vector_email.sent_timestamp = None
                vector_email.save()
            vector_email.set_state(VectorEmail.READY)

        return 'Success'

    def _pause_engagement(self):
        """ Set all VectorEmails in this Engagement that are currently in the
        VectorEmail.READY state and not flagged as being in a custom_state to
        VectorEmail.PAUSED.
        Does not change Engagement state. """
        for vector_email in VectorEmail.objects.\
                filter(engagement=self,
                       custom_state=False,
                       state=VectorEmail.READY):
            try:
                vector_email.set_state(VectorEmail.PAUSED)
            except:
                logger.info('[ ! ] Unable to pause VectorEmail #{} in'
                            ' Engagment #{}'.format(vector_email.id, self.id))

        # Doing this at the set_state level would also work, but putting it
        # here is more specific, and makes testing more precise.
        self.unschedule_all_vector_emails()

    def get_result_statistics(self):
        """ Returns a tuple of mixed types of statistics in this format:
            VectorEmail count,
            (OPEN ResultEvents, ratio of OPEN ResultEvents to VectorEmails),
            (CLICK ResultEvents, ratio of CLICK ResultEvents to VectorEmails),
            (SUBMIT ResultEvents, ratio of SUBMIT ResultEvents to VectorEmails)
        """
        eng_vemails = VectorEmail.objects.filter(engagement=self)
        vemail_count = eng_vemails.count()
        statistics = (vemail_count,)
        for each_type, _ in ResultEvent.CHOICES[1:]:
            events = eng_vemails.filter(result_event__event_type=each_type)
            event_count = float(events.distinct().count())
            try:
                ratio = '{:.0%}'.format(event_count / vemail_count)
            except ZeroDivisionError:
                ratio = '0%'
            statistics += ((int(event_count), ratio),)
        return statistics

    def save(self, *args, **kwargs):
        try:
            if not self.url_key:
                self.url_key = self.generate_url_key()
        except:
            pass
        super(Engagement, self).save(*args, **kwargs)

    def check_for_completion(self):
        unsent = VectorEmail.objects.filter(engagement=self,
                                            state__in=(VectorEmail.UNSCHEDULED,
                                                       VectorEmail.READY,
                                                       VectorEmail.ERROR))
        if unsent.exists() is False:
            self.set_state(Engagement.COMPLETE)

    def create_vector_emails(self):
        """ Create VectorEmails for all Targets in this Engagement.
        Subsequently calls Engagement.synchronize_vector_email_relations on
        this Engagement. """
        for target_list in self.target_lists.order_by('id'):
            for target in target_list.target.order_by('id'):
                # Using get_or_create prevents duplication due to the same
                # target being used in multiple target lists, but does not
                # prevent the use of the same email across multiple targets.
                vector_email, created = VectorEmail.objects.\
                                  get_or_create(engagement=self, target=target)
                if created:
                    vector_email.save()
        self.synchronize_vector_email_relations()

    def synchronize_vector_email_relations(self):
        """ Synchronize all VectorEmails' uncustomized relation keys to match
        this Engagement's respective relation keys. """
        VectorEmail.objects.\
            filter(engagement=self, custom_redirect_page=False).\
            update(redirect_page=self.redirect_page)
        VectorEmail.objects.\
            filter(engagement=self, custom_landing_page=False).\
            update(landing_page=self.landing_page)
        VectorEmail.objects.\
            filter(engagement=self, custom_email_template=False).\
            update(email_template=self.email_template)

    def unschedule_all_vector_emails(self):
        for vector_email in self.vector_email.all():
            vector_email.send_at = None
            vector_email.save()

    def determine_initial_sending_time(self):
        """ Combine this Engagement's start_type, start_date, and start_time
        to determine the earliest possible sending time.

        Does not change Engagement or VectorEmail states. """
        now = dj_tz.now()

        if self.start_type == 'immediate':
            initial_sending_time = now

        elif self.start_type == 'countdown':
            countdown_duration_as_time = dj_tz.datetime(1900, 1, 1, 0,
                                                        self.start_time.minute,
                                                        self.start_time.second)
            delta = countdown_duration_as_time - dj_tz.datetime(1900, 1, 1)
            initial_sending_time = now + delta

        elif self.start_type == 'specific_date':
            naive_sending_time = dj_tz.datetime(
                year=self.start_date.year,
                month=self.start_date.month,
                day=self.start_date.day,
                hour=self.start_time.hour,
                minute=self.start_time.minute,
                second=self.start_time.second
            )
            server_timezone = dj_tz.get_default_timezone()
            initial_sending_time = server_timezone.localize(naive_sending_time)

        if initial_sending_time < now:
            logger.info('[ ! ] Attempted to schedule for a datetime in the'
                        ' past: {}'.format(str(initial_sending_time)))
            return None

        return initial_sending_time

    def schedule_vector_emails(self, states_to_reschedule):
        """ Generate and apply a VectorEmail sending schedule using this
        Engagement's start_type, start_time, schedule, and vector_email data.

        Does not change Engagement.state or VectorEmail.state. """
        vector_emails = self.vector_email.filter(
            engagement=self,
            custom_send_at=False,
            state__in=states_to_reschedule
        ).order_by('id')

        number_to_schedule = vector_emails.count()
        if number_to_schedule < 1:
            message = '{} events scheduled for Engagement #{}'
            raise ValueError(message.format(number_to_schedule, self.id))

        initial_sending_time = self.determine_initial_sending_time()

        scheduled_times = self.schedule.calculate_sending_times(
            initial_sending_time,
            number_to_schedule
        )

        for index, vector_email in enumerate(list(vector_emails)):
            vector_email.update_schedule(scheduled_times[index])


class OAuthEngagement(Engagement):
    # This needs to be added after the OAuthEngagement is created, but
    # before it is saved, similar to a ManyToManyField.
    oauth_consumer = models.ForeignKey('OAuthConsumer',
                                       null=True,
                                       related_name='oauth_engagements')


class OAuthConsumer(models.Model):
    name = models.CharField(max_length=256, null=True)
    description = models.TextField(null=True, blank=True)
    client_id = models.CharField(max_length=256)
    client_secret = models.CharField(max_length=256)
    scope = models.CharField(max_length=256)
    callback_url = models.CharField(max_length=256)
    bounce_url = models.CharField(max_length=256)

    def __unicode__(self):
        return self.name


class OAuthResult(models.Model):
    timestamp = models.DateTimeField(null=True)
    userAgent = models.CharField(max_length=255, null=True)
    ip = models.GenericIPAddressField(null=True)
    email = models.CharField(max_length=255, null=True)
    oauth_engagement = models.ForeignKey(OAuthEngagement,
                                         null=True,
                                         blank=True,
                                         on_delete=models.SET_NULL,
                                         related_name='oauth_results')
    target = models.ForeignKey(Target,
                               null=True,
                               blank=True,
                               on_delete=models.SET_NULL,
                               related_name='oauth_results')
    consumer = models.ForeignKey(OAuthConsumer,
                                 null=True,
                                 blank=True,
                                 on_delete=models.CASCADE,
                                 related_name='oauth_results')
    credentials = CredentialsField()

    def __unicode__(self):
        return '{}'.format(self.email)

    def remove_files(self):
        for each in self.plunder.filter(oauth_result__id=self.id):
            try:
                each.delete()
            except Exception as error:
                logger.info('Error while deleting files'
                            ' for OAuthResult #{}: {}'.format(self.id, error))

    def delete(self, *args, **kwargs):
        self.remove_files()
        result = super(OAuthResult, self).delete(*args, **kwargs)
        return result


class Plunder(models.Model):
    oauth_result = models.ForeignKey(OAuthResult, null=True, blank=True,
                                     on_delete=models.CASCADE,
                                     related_name='plunder')
    path = models.CharField(max_length=255, null=True, blank=True)
    file_id = models.CharField(max_length=255, null=True, blank=True)
    filename = models.CharField(max_length=255, null=True, blank=True)
    mimetype = models.CharField(max_length=255, null=True, blank=True)
    last_modified = models.DateTimeField(null=True, blank=True)
    data = models.TextField(null=True)

    def __unicode__(self):
        return '#{}: {}'.format(self.id, self.filename)

    def remove_file(self):
        if os.path.exists(self.path):
            version_directory = os.path.dirname(self.path)
            file_id_directory = os.path.dirname(version_directory)
            oa_result_id_directory = os.path.dirname(file_id_directory)

            # Be very careful when altering paths.
            assert os.path.split(version_directory)[1].isdigit()
            assert os.path.split(oa_result_id_directory)[1].isdigit()
            shutil.rmtree(version_directory)
            logging.info('[ - ] Deleted: {}'.format(version_directory))

            # If they're empty, delete the two upper directories, in order.
            for each_directory in (file_id_directory, oa_result_id_directory):
                if len(os.listdir(each_directory)) == 0:
                    shutil.rmtree(each_directory)
                    logging.info('[ - ] Deleted: {}'.format(each_directory))
            message = '[ - ] Deleted: {}'.format(self.path)
        else:
            message = '[ ! ] Nonexistent path: {}'.format(self.path)

        return message

    def delete(self, *args, **kwargs):
        try:
            message = self.remove_file()
        except Exception as error:
            message = '[ ! ] Error while deleting {}: {}'.format(self.path,
                                                                 error)
        logging.info(message)

        return super(Plunder, self).delete(*args, **kwargs)


class ShoalScrapeCreds(models.Model):
    name = models.CharField(max_length=255, null=True, default='')
    username = models.CharField(max_length=255, null=True)
    password = models.CharField(max_length=255, null=True)
    scraper_user_agent = models.ForeignKey(ScraperUserAgent,
                                           null=True, blank=True,
                                           on_delete=models.SET_NULL,
                                           related_name='shoalscrape_creds')

    def __unicode__(self):
        return self.name


class ShoalScrapeTask(models.Model):
    ALL_STATES = (0, 1, 2, 3, 4)
    NOT_STARTED = 0
    IN_PROGRESS = 1
    PAUSED = 2
    ERROR = 3
    COMPLETE = 4
    STATE_CHOICES = ((NOT_STARTED, 'Not Started'),
                     (IN_PROGRESS, 'In Progress'),
                     (PAUSED, 'Paused'),
                     (ERROR, 'Error'),
                     (COMPLETE, 'Complete'))

    state = models.SmallIntegerField(choices=STATE_CHOICES,
                                     editable=False,
                                     default=NOT_STARTED)
    shoalscrape_creds = models.ForeignKey(ShoalScrapeCreds, null=True,
                                          related_name='shoalscrape_tasks')
    periodic_task = models.ForeignKey(PeriodicTask, null=True, blank=True)
    company = models.CharField(max_length=255, null=True)
    domain = models.CharField(max_length=255, null=True)
    company_linkedin_id = models.CharField(max_length=255, null=True)
    path = models.CharField(max_length=255, null=True, blank=True)
    last_started_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(null=True, blank=True, default='')
    current_task_id = models.CharField(max_length=36, null=True,
                                       blank=True, default='')

    def __unicode__(self):
        return self.company

    @property
    def status(self):
        return (self.state, self.error)

    def delete(self, *args, **kwargs):
        """
        Attempt to terminate the current ShoalScrapeTask's Celery task and then
        attempt to delete its PeriodicTask. If either fails for any reason,
        skip ahead and delete the ShoalScrapeTask instance.

        Does not delete any ShoalScrape log files.
        """
        try:
            self.terminate_task()
            self.periodic_task.delete()
        except:
            pass
        return super(ShoalScrapeTask, self).delete(*args, **kwargs)

    def set_state(self, new_state):
        self.state, old_state = new_state, self.state
        self.save()

        # Terminate task must not be called inside set_state because there are
        # some instances where attempting to terminate a not-yet-running task
        # can cause problems with Celery not properly revoking the task.
        if new_state in (ShoalScrapeTask.NOT_STARTED,
                         ShoalScrapeTask.PAUSED,
                         ShoalScrapeTask.ERROR,
                         ShoalScrapeTask.COMPLETE):
            self.terminate_task()

        elif new_state == ShoalScrapeTask.IN_PROGRESS and \
                old_state != ShoalScrapeTask.IN_PROGRESS:
            self.start_shoal_scrape_task()

        if new_state != ShoalScrapeTask.ERROR:
            self.error = ''
            self.save()

    def toggle_task(self):
        if self.state == ShoalScrapeTask.IN_PROGRESS:
            self.set_state(ShoalScrapeTask.PAUSED)
            return False

        elif self.state in (ShoalScrapeTask.NOT_STARTED,
                            ShoalScrapeTask.ERROR,
                            ShoalScrapeTask.PAUSED,
                            ShoalScrapeTask.COMPLETE):
            self.set_state(ShoalScrapeTask.IN_PROGRESS)
            return True

    def start_shoal_scrape_task(self):
        self.initialize_task()
        self.last_started_at = datetime.datetime.now()
        self.save()

        ptask = self.periodic_task
        ptask.enabled = True
        ptask.description = 'Started'
        ptask.save()
        now = datetime.datetime.now()
        ptask.last_run_at = now
        ptask.save()
        with open(self.path, 'a+b') as log_file:
            log_entry = '\n\n[{}] [ ^ ] Task initiated.\n\n'.format(now)
            log_file.write(log_entry)

    def stop_shoal_scrape_task(self):
        ptask = self.periodic_task
        ptask.enabled = False
        ptask.description = 'Stopped'
        ptask.save()

    def terminate_task(self, log_info=''):
        # Users might need to terminate a task that has lost its PeriodicTask.
        # Stopping Celery is more important than breaking if
        # stop_shoal_scrape_task fails.
        try:
            self.stop_shoal_scrape_task()
        except:
            pass
        # Reference: http://stackoverflow.com/a/8924116
        # Note: This issues SIGTERM. ShoalScrape is expected to handle that.
        if self.current_task_id:
            with open(self.path, 'a+b') as log_file:
                log_info += ('\n\n[{}] [ . ] Task terminated.'
                             ' Terminated celery task ID: {}\n\n')
                log_file.write(log_info.format(datetime.datetime.now(),
                                               self.current_task_id))
            self.current_task_id = ''
            self.save()
            # terminate_task is called by the revoked task, so this comes last:
            revoke(self.current_task_id, terminate=True)
        else:
            message = ('ShoalScrapeTask #{} terminate_task attempted and'
                       ' failed due to no current_task_id, or pause was called'
                       ' before the task was started.'.format(self.id))
            logger.info(message)
            with open(self.path, 'a+b') as log_file:
                log_info += '\n\n[{}] [ ! ] {}\n\n'
                log_file.write(log_info.format(datetime.datetime.now(),
                                                message))
        self.current_task_id = ''
        self.save()

    def set_log_file_path(self):
        assert self.id, "ShoalScrapeTask must be saved to be given a path"
        assert self.company, "Log file path creation requires a valid company"
        assert settings.SHOALSCRAPE_RESULTS_PATH

        storage_directory = os.path.join(settings.SHOALSCRAPE_RESULTS_PATH,
                                         str(self.id))
        if not os.path.exists(storage_directory):
            os.makedirs(storage_directory)
        log_file_name = '{}.log'.format(self.company.lower().replace(" ", "_"))
        path = os.path.join(storage_directory, log_file_name)

        self.path = path
        self.save()

    def initialize_task(self):
        if self.periodic_task is not None:
            internal_interval = self.periodic_task.interval
            self.periodic_task.delete()
            internal_interval.delete()  # Clear up unused IntervalSchedules

        ptask_name = 'shoalscrape_task_{}'.format(self.id)

        internal_interval = IntervalSchedule(every=20, period='seconds')
        internal_interval.save()

        # Of the PeriodicTask run-state information, only `enabled` should be
        # set here, because the default is True and that causes the task to be
        # started before Sandbar toggles it on.
        ptask = PeriodicTask(
            name=ptask_name,
            task='client.tasks.start_shoalscrape_task',
            interval=internal_interval,
            enabled=False,
            args=[self.id],
            kwargs={}
        )
        ptask.save()
        self.periodic_task = ptask
        self.save()
