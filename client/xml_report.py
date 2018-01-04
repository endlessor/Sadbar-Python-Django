from lxml.etree import Element, SubElement, tostring

from django.contrib.auth.decorators import login_required
from django.http.response import HttpResponse

from client.models import (Engagement, Campaign, Client, ResultEvent,
                           OAuthResult)


@login_required
def serve_xml_report(request, engagement_id=None, campaign_id=None, client_id=None):
    return create_xml_report_response(engagement_id=engagement_id, campaign_id=campaign_id, client_id=client_id)


def create_xml_report_response(engagement_id=None, campaign_id=None, client_id=None):
    xml_tree = generate_xml_report(engagement_id=engagement_id, campaign_id=campaign_id, client_id=client_id)
    data = tostring(xml_tree, pretty_print=True)
    response = HttpResponse(data, content_type="application/xhtml+xml")
    if engagement_id is not None:
        disposition = 'attachment; filename=engagement_{}.xml'.format(engagement_id)
    elif campaign_id is not None:
        disposition = 'attachment; filename=campaign_{}.xml'.format(campaign_id)
    elif client_id is not None:
        disposition = 'attachment; filename=client_{}.xml'.format(client_id)
    response['Content-Disposition'] = disposition
    return response


def generate_xml_report(engagement_id=None, campaign_id=None, client_id=None):
    try:
        if client_id is not None:
            client = Client.objects.get(id=client_id)
            campaigns = Campaign.objects.filter(client__id=client_id)
            engagements = Engagement.objects.filter(campaign__client__id=client_id)

        elif campaign_id is not None:
            client = Client.objects.get(campaign__id=campaign_id)
            campaigns = Campaign.objects.filter(id=campaign_id)
            engagements = Engagement.objects.filter(campaign__id=campaign_id)

        elif engagement_id is not None:
            client = Client.objects.get(campaign__engagement__id=engagement_id)
            campaigns = Campaign.objects.filter(engagement__id=engagement_id)
            engagements = Engagement.objects.filter(id=engagement_id)

        return build_xml(client, campaigns, engagements)

    except Engagement.DoesNotExist:
        xml_engagement = Element('engagement')
        xml_engagement.text = str('Engagement {} not found'.format(engagements[0].id))
        return xml_engagement
    except Campaign.DoesNotExist:
        xml_campaign = Element('campaign')
        xml_campaign.text = str('No campaign found for engagement {}'.format(engagements[0].id))
        return xml_campaign
    except Client.DoesNotExist:
        xml_client = Element('client')
        xml_client.text = str('No client found for engagement {}'.format(engagements[0].id))
        return xml_client


def build_xml(client, campaigns, engagements):
    xml_client = Element('client', {'id': str(client.id),
                                    'name': str(client.name),
                                    'url': str(client.url),
                                    'timezone': str(client.default_time_zone)})

    for campaign in campaigns:
        xml_campaign = SubElement(xml_client, 'campaign',
                                  {'id': str(campaign.id),
                                   'title': str(campaign.name)})
        campaign_description = SubElement(xml_campaign, 'description')
        campaign_description.text = str(campaign.description)

        for engagement in engagements.filter(campaign=campaign):
            phishing_domain = engagement.domain
            oauth_consumer = engagement.oauth_consumer
            schedule = engagement.schedule
            sender = engagement.email_server
            email_template = engagement.email_template
            landing_page = engagement.landing_page
            redirect_page = engagement.redirect_page

            engagement_type = 'oauth' if engagement.is_oauth else 'phishing'
            xml_engagement = SubElement(xml_campaign, 'engagement',
                                        {'id': str(engagement.id),
                                         'type': engagement_type,
                                         'title': str(engagement.name)})
            engagement_description = SubElement(xml_engagement, 'description')
            engagement_description.text = str(engagement.description)

            # OAuthConsumer / PhishingDomain
            if engagement.is_oauth:
                xml_oauth_consumer = SubElement(xml_engagement, 'oauth-consumer',
                                                {'id': str(oauth_consumer.id),
                                                 'callback-url': str(oauth_consumer.callback_url)})
            elif phishing_domain is not None:
                xml_phishing_domain = SubElement(xml_engagement, 'phishing-domain',
                                                 {'id': str(engagement.id),
                                                  'protocol': str(phishing_domain.protocol),
                                                  'domain': str(phishing_domain.domain_name),
                                                  'path': str(engagement.path)})
            else:
                xml_phishing_domain = SubElement(xml_engagement, 'phishing-domain',
                                                 {'id': str('None'),
                                                  'protocol': str('None'),
                                                  'path': str(engagement.path)})
                xml_phishing_domain.text = str('No phishing domain found for'
                                               ' engagement {}'.format(engagement.id))

            # Schedule
            if schedule is not None:
                xml_schedule = SubElement(xml_engagement, 'schedule',
                                          {'id': str(schedule.id),
                                           'is_default': str(schedule.is_default),
                                           'interval': str(schedule.interval),
                                           'excluded_dates': str(schedule.excluded_dates)})

                # ScheduleWindows
                for schedule_window in schedule.windows.all():
                    xml_schedule_window = SubElement(xml_schedule, 'schedule-window',
                                                     {'id': str(schedule_window.id),
                                                      'schedule': str(schedule_window.schedule.id),
                                                      'day_of_the_week': str(schedule_window.day_of_the_week),
                                                      'open_time': str(schedule_window.open_time),
                                                      'close_time': str(schedule_window.close_time)})

            else:
                xml_schedule = SubElement(xml_engagement, 'schedule')
                xml_schedule.text = str('No schedule found for engagement {}'.format(engagement.id))

            # EmailServer
            if sender is not None:
                xml_sender = SubElement(xml_engagement, 'sender',
                                        {'id': str(sender.id),
                                         'port': str(sender.port),
                                         'server': str(sender.host),
                                         'address': str(sender.login)})
            else:
                xml_sender = SubElement(xml_engagement, 'sender')
                xml_sender.text = str('No sender found for engagement {}'.format(engagement.id))

            # EmailTemplate
            if email_template is not None:
                xml_email_template = SubElement(xml_engagement, 'email-template',
                                                {'id': str(email_template.id),
                                                 'name': str(email_template.name)})
                email_template_description = SubElement(xml_email_template, 'description')
                email_template_description.text = str(email_template.description)
                email_template_from = SubElement(xml_email_template, 'from')
                email_template_from.text = str(email_template.from_header)
                email_template_subject = SubElement(xml_email_template, 'subject')
                email_template_subject.text = str(email_template.subject_header)
            else:
                xml_email_template = SubElement(xml_engagement, 'email-template')
                xml_email_template.text = str('No email template found for'
                                              ' engagement {}'.format(engagement.id))

            # LandingPage
            if landing_page is not None:
                xml_landing_page = SubElement(xml_engagement, 'landing-page',
                                              {'id': str(landing_page.id),
                                               'type': str(landing_page.page_type),
                                               'name': str(landing_page.name)})
                xml_landing_page.text = str(landing_page.url)
                landing_page_description = SubElement(xml_landing_page, 'description')
                landing_page_description.text = str(landing_page.description)
            elif engagement_type == 'phishing':
                xml_landing_page = SubElement(xml_engagement, 'landing-page')
                xml_landing_page.text = str('No landing page found for engagement {}'.format(engagement.id))

            # Redirect page
            if redirect_page is not None:
                xml_redirect_page = SubElement(xml_engagement, 'redirect-page',
                                              {'id': str(redirect_page.id),
                                               'type': str(redirect_page.page_type),
                                               'name': str(redirect_page.name)})
                xml_redirect_page.text = str(redirect_page.url)
                redirect_page_description = SubElement(xml_redirect_page, 'description')
                redirect_page_description.text = str(redirect_page.description)
            elif engagement_type == 'phishing':
                xml_redirect_page = SubElement(xml_engagement, 'redirect-page')
                xml_redirect_page.text = str('No redirect page found for engagement {}'.format(engagement.id))

            # Targets
            xml_targets = SubElement(xml_engagement, 'targets')

            for target_list in engagement.target_lists.all():
                for target in target_list.target.all():
                    xml_target = SubElement(xml_targets, 'target',
                                            {'id': str(target.id),
                                             'email': str(target.email),
                                             'firstname': str(target.firstname),
                                             'lastname': str(target.lastname),
                                             'list': str(target_list.nickname),
                                             'timezone': str(target.get_timezone())})

                    # TargetData
                    target_data = target.targetdatum_set.filter(target_list=target_list)
                    for target_datum in target_data:
                        xml_datum = SubElement(xml_target, target_datum.label,
                                               {'id': str(target_datum.id)})
                        xml_datum.text = str(target_datum.value)

                    # VectorEmails
                    vector_email = target.vector_email.get(engagement=engagement)
                    if vector_email is not None:
                        vector_email_status = vector_email.get_state_display().lower()
                        if vector_email_status == 'error':
                            err_code, err_text, err_suggestion = vector_email.error_details
                            # Many things can go wrong with error parsing, because
                            # errors during email sending can come in many formats.
                            try:
                                if err_suggestion is not None:
                                    error_text = '{} {}'.format(err_code, err_suggestion)
                                elif err_text is not None:
                                    error_text = '{} {}'.format(err_code, err_text)
                                else:
                                    error_text = vector_email.error
                            except:
                                error_text = vector_email.error
                            vector_email_status += ' - {}'.format(error_text)

                        xml_vector_email = SubElement(xml_target, 'vector-email',
                                                      {'id': str(vector_email.id),
                                                       'status': str(vector_email_status)})

                        # All "results" depend on the presence of a VectorEmail, but
                        # for simplicity they should not provide empty elements if no
                        # results were created.

                        # ResultEvents
                        xml_results = SubElement(xml_target, 'results')

                        for result_event in vector_email.result_event.order_by('-timestamp'):
                            event_type = result_event.get_event_type_display().lower()
                            xml_result_event = SubElement(xml_results, event_type,
                                                          {'id': str(result_event.id),
                                                           'time': str(result_event.timestamp),
                                                           'ip': str(result_event.ip),
                                                           'useragent': str(result_event.userAgent)})
                            if result_event.event_type == ResultEvent.SUBMIT:
                                result_event_login = SubElement(xml_result_event, 'login')
                                result_event_login.text = str(result_event.login)
                                result_event_password = SubElement(xml_result_event, 'password')
                                result_event_password.text = str(result_event.password)

                        # OAuthResults
                        oauth_results = OAuthResult.objects.filter(
                            oauth_engagement=engagement,
                            email=target.email
                        )
                        for oauth_result in oauth_results:
                            xml_oauth_result = SubElement(xml_results, 'oauth-grant',
                                                          {'id': str(oauth_result.id),
                                                           'time': str(oauth_result.timestamp),
                                                           'ip': str(oauth_result.ip),
                                                           'userAgent': str(oauth_result.userAgent),
                                                           'email': str(oauth_result.email)})
                            if oauth_result.target is not None:
                                xml_oauth_result.set('target', str(oauth_result.target.email))

                    else:
                        xml_vector_email = SubElement(xml_target, 'vector-email')
                        xml_vector_email.text = str('No vector email found for'
                                                    ' target {} in engagement {}'
                                                    ''.format(target.id, engagement.id))

    return xml_client
