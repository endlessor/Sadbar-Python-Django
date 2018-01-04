# -*- coding: utf-8 -*-
import datetime
import json
import re
from smtplib import SMTPRecipientsRefused

from celery import task
from celery.task.control import revoke
from celery.exceptions import Ignore
from celery.utils.log import get_task_logger
from djcelery.models import PeriodicTask
from django.utils import timezone as dj_tz
from django.core.mail import EmailMultiAlternatives
from django.core.mail.backends.smtp import EmailBackend
from django.template import Context
from django.template.loader import get_template
from django.db.models import Q
from oauth2client.client import OAuth2WebServerFlow

from helpers import split_and_clean_url
from models import (Engagement, Target, TargetDatum, VectorEmail,
                    ShoalScrapeTask)
from ShoalScrape import shoalscrape
from sandbar import settings

logger = get_task_logger(__name__)


def generateContent(target, engagement):
    ''' Compile email content personalized for a target in an engagement.
    Does not create or change VectorEmails.

    Return a hex-tuple containing all the information required to send an
    email in send_single_html_mail. '''

    # Support for customized VectorEmails' EmailTemplates.
    vector_email = VectorEmail.objects.get(engagement=engagement,
                                           target=target)
    if vector_email.custom_email_template and vector_email.email_template:
        et = vector_email.email_template
    else:
        et = engagement.email_template

    text_content = et.template

    target_dict = dict()

    target_dict['email'] = target.email
    target_dict['firstname'] = target.firstname
    target_dict['lastname'] = target.lastname
    target_dict['timezone'] = target.get_timezone()

    ref = target.encrypt_id(engagement.url_key)

    if engagement.is_oauth:
        try:
            oauth_consumer = engagement.oauth_consumer
        except:
            oauth_consumer = engagement.oauthengagement.oauth_consumer

        scope = oauth_consumer.scope.split('+')
        if 'email' not in scope:
            scope.append('email')

        # Refresh tokens will not be granted unless both access_type='offline'
        # and prompt='consent' are used.
        # Reference: http://stackoverflow.com/q/10827920/6516632
        flow = OAuth2WebServerFlow(client_id=oauth_consumer.client_id,
                                   client_secret=oauth_consumer.client_secret,
                                   scope=scope,
                                   redirect_uri=oauth_consumer.callback_url,
                                   state=ref,
                                   access_type='offline',
                                   prompt='consent')
        authorization_url = flow.step1_get_authorize_url()
        target_dict['url'] = authorization_url

        # Constructing tracking image links
        # The callback_url will contain a protocol and a domain name. Both will
        # need to be separated and stored to construct the URL containing the
        # referral ID.
        if oauth_consumer.callback_url.startswith('https://'):
            protocol = oauth_consumer.callback_url[:8]
            url = oauth_consumer.callback_url[8:]
        else:
            protocol = oauth_consumer.callback_url[:7]
            url = oauth_consumer.callback_url[7:]

        # Splitting on slashes keeps files and queries in the final segment.
        segmented_url = split_and_clean_url(url)

        # The domain will always be the first slash-split URL segment after the
        # protocol has been removed.
        domain = segmented_url[0]
        path = segmented_url[1:]

        path.insert(-1, ref)
        path = '/'.join(path)

        # Support for optional path query parameters.
        query_start_index = path.find('?')
        if query_start_index > -1:
            query = path[query_start_index:]
            path = path[:query_start_index]
        else:
            query = ''

        image_url = '{}{}/{}/1x1.png{}'.format(protocol, domain, path, query)

    else:
        open_redirect = engagement.open_redirect
        protocol = engagement.domain.protocol
        domain = engagement.domain.domain_name
        path = engagement.path

        # Splitting on slashes keeps files and queries in the final segment.
        segmented_path = split_and_clean_url(path)
        segmented_path.insert(-1, ref)
        path = '/'.join(segmented_path)

        # Support for optional path query parameters.
        query_start_index = path.find('?')
        if query_start_index > -1:
            query = path[query_start_index:]
            path = path[:query_start_index]
        else:
            query = ''

        if open_redirect:
            target_dict['url'] = '{}{}/{}{}'.format(open_redirect.url,
                                                    domain, path, query)
        else:
            target_dict['url'] = '{}://{}/{}{}'.format(protocol, domain, path,
                                                       query)

        image_url = '{}://{}/{}/1x1.png{}'.format(protocol, domain, path,
                                                  query)

    target_lists = target.targetlist_set.filter(engagement=engagement)
    for target_list in target_lists:
        target_data = TargetDatum.objects.filter(target=target,
                                                 target_list=target_list)
        for datum in target_data:
            target_dict.update({datum.label: datum.value})

    from_header = et.from_header
    subject_header = et.subject_header
    for key, val in target_dict.iteritems():
        if key and val:
            pattern = r"\[\#\[" + '{}'.format(key) + r"\]\#\]"
            text_content = re.sub(pattern, val, text_content)
            from_header = re.sub(pattern, val, from_header)
            subject_header = re.sub(pattern, val, subject_header)
    text_content = re.sub(r"\[\#\[\w+\]\#\]", '', text_content)
    text_content = re.sub(r"(?:src=)(\'|\"|)(?:\/|)(images)",
                          'src=\g<1>%s://%s/\g<2>' % (protocol, settings.HOST),
                          text_content)
    from_header = re.sub(r"\[\#\[\w+\]\#\]", '', from_header)
    subject_header = re.sub(r"\[\#\[\w+\]\#\]", '', subject_header)

    htmly = get_template('email.html')

    d = Context({'email_text': text_content,
                 'image_url': image_url})
    html_content = htmly.render(d)
    from_address = engagement.email_server.login

    # All of these are strings.
    # The return value must be fully JSON-serializable by djcelery.
    msg = (subject_header, text_content, html_content,
           '%s <%s>' % (from_header, from_address),
           (target_dict['email'],), from_address)

    return msg


def interpret_email_error(error):
    """ Take a VectorEmail error and see if it has the signature of certain
    SMTP errors with known causes and solutions. If a known error is found,
    create a human-readable error diagnosis and solution suggestion. Place
    both the suggestion and a stringified representation of the original
    error in a dictionary and JSONify it.
    Returns a JSONified string. """
    error_container = dict()
    suggestion = None

    if type(error) == SMTPRecipientsRefused:
        recipient = error.recipients.keys()[0]
        smtp_error_code, error_string = error.recipients[recipient]
        if smtp_error_code == 553 and error_string[:6] == '5.1.2 ':
            suggestion = ('The recipient address "{}" is not a valid email'
                          ' address.'.format(recipient))
        elif smtp_error_code == 553 and error_string[:6] == '5.7.1 ':
            suggestion = ('The "From Header" for this email\'s template should'
                          ' not contain an email address that is not identical'
                          ' to the "Login" address used by this email\s email'
                          ' server.')

    # Collapse the error into a JSON-serializable representation:
    try:
        error_container['error'] = json.dumps(error.recipients)
    except:
        error_container['error'] = str(error)
    try:
        error_container['suggestion'] = suggestion
        return json.dumps(error_container)
    except:
        return str(error_container)


@task(ignore_result=True)
def send_single_html_mail(vector_email_id, fail_silently=False):
    try:
        vector_email = VectorEmail.objects.get(id=vector_email_id)
    except VectorEmail.DoesNotExist:
        # Prevents Celery log spam for the defunct task.
        ptask_identifier = 'send_vemail__v{}_'.format(vector_email_id)
        ptask = PeriodicTask.objects.get(name__contains=ptask_identifier)
        send_error_log_template = ('VE #{} not found while sending.'
                                   ' PeriodicTask #{}, {}, has been deleted.')
        logger.info(send_error_log_template.format(vector_email_id,
                                                   ptask.id,
                                                   ptask.name))
        ptask.delete()
        raise Ignore()

    engagement = vector_email.engagement
    target = Target.objects.get(vector_email=vector_email)

    if vector_email.send_at_passed is True:
        vector_email.set_state(VectorEmail.SEND_MISSED)
        engagement.check_for_completion()

        send_missed_log_template = 'VE #{} send_at MISSED: {}, Target TZ {}'
        logger.info(send_missed_log_template.format(vector_email.id,
                                                    vector_email.send_at,
                                                    target.get_timezone()))
        return

    sending_log_template = 'Sending VE #{} with send_at {}, Target TZ {}'
    logger.info(sending_log_template.format(vector_email.id,
                                            vector_email.send_at,
                                            target.get_timezone()))

    email_server = engagement.email_server
    connection = EmailBackend(host=email_server.host,
                              port=int(email_server.port),
                              username=email_server.login,
                              password=email_server.password,
                              use_tls=email_server.use_tls)

    datatuple = generateContent(target, engagement)
    subject, text, html, from_email, recipient, from_address = datatuple
    message = EmailMultiAlternatives(subject, text, from_email, recipient,
                                     headers={'Reply-To': from_address})
    message.attach_alternative(html, 'text/html')

    sent = 0
    try:
        sent = connection.send_messages((message,))
        server_tz = dj_tz.get_default_timezone()
        server_now = server_tz.localize(datetime.datetime.now())
        vector_email.sent_timestamp = server_now
        vector_email.error = ''
        vector_email.save()
        vector_email.set_state(VectorEmail.SENT)
        engagement.check_for_completion()
    except Exception as e:
        vector_email.set_state(VectorEmail.ERROR)
        vector_email.error = interpret_email_error(e)
        vector_email.save()
        engagement.set_state(Engagement.ERROR)
        send_error_log_template = 'VE #{} task had an error: {}'
        logger.info(send_error_log_template.format(vector_email.id, e))
        raise Ignore()
    return sent


@task(ignore_result=True)
def start_shoalscrape_task(shoalscrape_task_id, fail_silently=False):
    # Reference: http://stackoverflow.com/a/8096086
    # Allows us to terminate this task's execution arbitrarily through Django.
    # This section should come as early as possible.
    current_task_id = start_shoalscrape_task.request.id

    already_running_tasks = ShoalScrapeTask.objects.filter(
        id=shoalscrape_task_id
    ).exclude(
        current_task_id=''
    )

    # Checking same_db_id_and_different_task_id does block multiple workers.
    if already_running_tasks.exists():
        other_celery_ids = [t.current_task_id for t in already_running_tasks]
        shoalscrape_ids = [t.id for t in already_running_tasks]
        error_message = ('[ ! ] ShoalScrapeTask(s) {} attempted to start a'
                         ' Celery worker with ID {} while they already had'
                         ' Celery workers with IDs {}. Terminating worker with'
                         ' Celery task ID {}'.format(shoalscrape_ids,
                                                     current_task_id,
                                                     other_celery_ids,
                                                     current_task_id))
        revoke(current_task_id, terminate=True)
        logger.info(error_message)
        raise Ignore()

    try:
        shoalscrape_task = ShoalScrapeTask.objects.get(id=shoalscrape_task_id)
    except ShoalScrapeTask.DoesNotExist:
        # Prevents Celery log spam for the defunct task. (different from VE)
        ptask_identifier = 'shoalscrape_task_{}'.format(shoalscrape_task_id)
        ptask = PeriodicTask.objects.get(name=ptask_identifier)
        task_error_log_template = ('ShoalScrapeTask #{} not found while '
                                   'starting. PeriodicTask #{}, {}, has been '
                                   'deleted.')
        logger.info(task_error_log_template.format(shoalscrape_task_id,
                                                   ptask.id,
                                                   ptask.name))
        ptask.delete()
        raise Ignore()

    # This should come as early as possible after checking that the task is not
    # duplicated (ie, once current_task_id and shoalscrape_task are available):
    shoalscrape_task.current_task_id = current_task_id
    shoalscrape_task.save()

    ptask = shoalscrape_task.periodic_task
    # Prevents any other Celery workers from starting a task with the same ID:
    ptask.last_run_at = datetime.datetime.now() + datetime.timedelta(days=9999)
    ptask.save()
    shoalscrape_task.save()

    active_tasks = ShoalScrapeTask.objects.filter(
        Q(periodic_task__enabled=True) | Q(state=ShoalScrapeTask.IN_PROGRESS)
    ).exclude(id=shoalscrape_task_id)

    # Checking active_tasks does not protect against multiple Celery workers
    # starting for the same ShoalScrapeTask; rather, it prevents multiple
    # ShoalScrapeTasks from starting.
    if active_tasks.exists():
        ids = [each.id for each in active_tasks]
        error_message = ('[ ! ] Started while other ShoalScrape tasks were '
                         'running: {}'.format(ids))
        logger.info(error_message)
        shoalscrape_task.error = error_message
        shoalscrape_task.save()
        shoalscrape_task.set_state(ShoalScrapeTask.ERROR)
        shoalscrape_task.terminate_task(log_info=error_message)
        raise Ignore()

    server_tz = dj_tz.get_default_timezone()
    server_now = server_tz.localize(datetime.datetime.now())
    shoalscrape_task.last_started_at = server_now
    shoalscrape_task.save()

    task_log_template = '[ + ] Attempting to start ShoalScrapeTask #{} at {}'
    logger.info(task_log_template.format(shoalscrape_task.id,
                                         shoalscrape_task.last_started_at))

    results = 0
    try:
        company = shoalscrape_task.company
        domain = shoalscrape_task.domain
        company_linkedin_id = shoalscrape_task.company_linkedin_id
        log_file_path = shoalscrape_task.path
        creds = shoalscrape_task.shoalscrape_creds
        user_agent = None
        if creds.scraper_user_agent:
            user_agent = creds.scraper_user_agent.user_agent_data
        username = creds.username
        password = creds.password
        results = shoalscrape.webserver_main(company, company_linkedin_id,
                                             domain, log_file_path, user_agent,
                                             username=username,
                                             password=password,
                                             scan_profiles=False,
                                             brute_force_emails=False)
        shoalscrape_task.set_state(ShoalScrapeTask.COMPLETE)
        shoalscrape_task.current_task_id = ''
        shoalscrape_task.save()

    except Exception as e:
        error = ('[ ! ] ShoalScrapeTask'
                 ' #{} had an error: {}'.format(shoalscrape_task.id, e))
        shoalscrape_task.set_state(ShoalScrapeTask.ERROR)
        shoalscrape_task.terminate_task(log_info=error)
        shoalscrape_task.error = error
        shoalscrape_task.save()
        logger.info(error)
        raise Ignore()

    return results
