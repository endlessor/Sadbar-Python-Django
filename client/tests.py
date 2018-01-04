import calendar
import datetime
import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.utils import timezone as dj_tz
from django_webtest import WebTest

# http://stackoverflow.com/a/33369349
from celery import current_app

from client.models import (SiteSettings, EmailServer, Schedule, ScheduleWindow,
                           LandingPage, EmailTemplate, Client, Campaign,
                           ResultEvent, Target, TargetList, VectorEmail,
                           Engagement, ScraperUserAgent, PhishingDomain)
from client.utils import b64_encrypt, b64_decrypt

User = get_user_model()


class SandbarTest(WebTest):

    def setUp(self):
        settings.CELERY_ALWAYS_EAGER = True
        current_app.conf.CELERY_ALWAYS_EAGER = True

        self.nonstaff_user = User(
            username='nonstaff.user',
            password='nonstaff.user',
            is_staff=False,
            is_superuser=False)
        self.nonstaff_user.save()

        self.staff_user = User(
            username='staff.user',
            password='staff.user',
            is_staff=True,
            is_superuser=False)
        self.staff_user.save()

        self.superuser = User(
            username='super.user',
            password='super.user',
            is_staff=True,
            is_superuser=True)
        self.superuser.save()

        # Client default_time_zone should not match any Targets' TZs for tests.
        self.client = Client(
            name=u'Test Client',
            url=u'http://www.testclient.com/',
            default_time_zone='Etc/GMT+11'
        )
        self.client.save()
        self.campaign = Campaign(
            name=u'Test Campaign',
            description=u'The test campaign description.',
            client=self.client
        )
        self.campaign.save()

        self.now = dj_tz.now()

        self.schedule_one = Schedule(
            name=u'Test Schedule #1 (30 second interval)',
            interval=30,
            excluded_dates=[]
        )
        self.schedule_one.save()

        self.schedule_two = Schedule(
            name=u'Test Schedule #2 (5 minute interval)',
            interval=300,
            excluded_dates=[]
        )
        self.schedule_two.save()

        self.today = self.now
        self.tomorrow = self.now + dj_tz.timedelta(days=1)

        # self.today is a datetime.date, but self.now must be non-naive.
        self.the_datetime_after_tomorrow = self.now + dj_tz.timedelta(days=2)

        # Making a ScheduleWindow that's only open two days from now prevents
        # test failures that occur when the test is run right before midnight.
        self.weekday_ordinal_after_tomorrow = self.the_datetime_after_tomorrow.weekday()
        self.weekday_after_tomorrow = calendar.day_name[self.weekday_ordinal_after_tomorrow].lower()

        self.three_datetime_hours_from_the_datetime_after_tomorrow = self.the_datetime_after_tomorrow + dj_tz.timedelta(hours=3)
        self.three_clock_hours_from_now = datetime.time(
            hour=self.three_datetime_hours_from_the_datetime_after_tomorrow.hour,
            minute=self.three_datetime_hours_from_the_datetime_after_tomorrow.minute,
            second=self.three_datetime_hours_from_the_datetime_after_tomorrow.second
        )
        self.six_datetime_hours_from_the_datetime_after_tomorrow = self.the_datetime_after_tomorrow + dj_tz.timedelta(hours=6)
        self.six_clock_hours_from_now = datetime.time(
            hour=self.six_datetime_hours_from_the_datetime_after_tomorrow.hour,
            minute=self.six_datetime_hours_from_the_datetime_after_tomorrow.minute,
            second=self.six_datetime_hours_from_the_datetime_after_tomorrow.second
        )

        self.schedule_with_schedule_window = Schedule(
            name=u'Test Schedule, with Schedule Window',
            interval=10,
            excluded_dates=[]
        )
        self.schedule_with_schedule_window.save()

        self.schedule_window = ScheduleWindow(
            schedule=self.schedule_with_schedule_window,
            day_of_the_week=self.weekday_after_tomorrow,
            open_time=self.three_clock_hours_from_now,
            close_time=self.six_clock_hours_from_now
        )
        self.schedule_window.save()

        self.schedule_with_excluded_dates = Schedule(
            name=u'Test Schedule, with Excluded Dates',
            interval=10,
            excluded_dates=[self.today, self.tomorrow]
        )
        self.schedule_with_excluded_dates.save()

        self.testserver_domain = PhishingDomain(
            domain_name='testserver'
        )
        self.testserver_domain.save()

        self.email_server = EmailServer(
            host=u'smtp.gmail.com',
            port=u'587',
            use_tls=True,
            login=u'rhinosec.test.bf.0@gmail.com',
            password=u'rhinosec test bf 0'
        )
        self.email_server.save()

        self.email_template = EmailTemplate(
            name=u'Test Email Template',
            description=u'It\s a test email template.',
            from_header=u'Member Services',
            subject_header=u'You\'ve got mail',
            template=u'<h1>IT\'S ALIVE!</h1>'
        )
        self.email_template.save()

        self.scraper_user_agent = ScraperUserAgent(
            name=u'Test Scraper User Agent',
            user_agent_data='Testzilla/5.0'
        )
        self.scraper_user_agent.save()

        self.landing_page = LandingPage(
            name=u'Capitestla One',
            description=u'It\s a test landing page.',
            url=u'testserver/capitestla_one',
            path=os.path.join(
                settings.BASE_DIR,
                'test_data',
                'test_landing_page.html'
            ),
            is_redirect_page=False,
            status=1,
            page_type='manual',
            scraper_user_agent=self.scraper_user_agent
        )
        self.landing_page.save()

        self.redirect_page = LandingPage(
            name=u'Capitestla One Redirect',
            description=u'It\s a test redirect page.',
            url=u'testserver/capitestla_one/redirect',
            path=os.path.join(
                settings.BASE_DIR,
                'test_data',
                'test_redirect_page.html'
            ),
            is_redirect_page=True,
            status=1,
            page_type='manual',
            scraper_user_agent=self.scraper_user_agent
        )
        self.redirect_page.save()

        self.target_1 = Target(
            email=u'sb_test_0@sb_test.com',
            firstname=u'Teston',
            lastname=u'McTesterson'
        )
        self.target_1.save()

        self.target_2 = Target(
            email=u'sb_test_1@sb_test.com',
            firstname=u'Testa',
            lastname=u'Testirsdottir'
        )
        self.target_2.save()

        self.target_list = TargetList(
            nickname=u'Test Target List',
            description=u'Test target list description.',
            client=self.client
        )
        self.target_list.save()
        self.target_list.target.add(self.target_1)
        self.target_list.target.add(self.target_2)
        self.target_list.save()

        # The following targets are declared explicitly rather than dynamically
        # in order to emphasize certain specific timezone offsets that must be
        # carefully tested.

        # Should fall through to the Target's Client's default_time_zone (-11).
        self.no_tz_info_target = Target(
            email=u'notzinfo@gmail.com',
            firstname=u'No',
            lastname=u'Tzinfo'
        )
        self.no_tz_info_target.save()

        # GMT negative increment lower bound
        self.gmt_m14_target = self.make_timezone_target('Etc/GMT-14')
        self.gmt_m14_target.save()

        # Second negative GMT offset target
        self.gmt_m5_target = self.make_timezone_target('Etc/GMT-5')
        self.gmt_m5_target.save()

        # Targets around and at the sending deadline
        self.gmt_m1_target = self.make_timezone_target('Etc/GMT-1')
        self.gmt_m1_target.save()
        self.gmt_m0_target = self.make_timezone_target('Etc/GMT-0')
        self.gmt_m0_target.save()
        self.gmt_p1_target = self.make_timezone_target('Etc/GMT+1')
        self.gmt_p1_target.save()

        # PST+2 / PDT+1
        self.gmt_p6_target = self.make_timezone_target('Etc/GMT+6')
        self.gmt_p6_target.save()

        # PDT+0 / PST+1
        self.gmt_p7_target = self.make_timezone_target('Etc/GMT+7')
        self.gmt_p7_target.save()

        # PST+0 / PDT-1
        self.gmt_p8_target = self.make_timezone_target('Etc/GMT+8')
        self.gmt_p8_target.save()

        # PST-1 / PDT-2
        self.gmt_p9_target = self.make_timezone_target('Etc/GMT+9')
        self.gmt_p9_target.save()

        # GMT positive increment upper bound
        self.gmt_p12_target = self.make_timezone_target('Etc/GMT+12')
        self.gmt_p12_target.save()

        self.large_target_list = TargetList(
            nickname=u'large-target-list',
            description=u'Large test TargetList.',
            client=self.client
        )
        self.large_target_list.save()
        self.large_target_list.target.add(self.no_tz_info_target)
        self.large_target_list.target.add(self.gmt_m14_target)
        self.large_target_list.target.add(self.gmt_m5_target)
        self.large_target_list.target.add(self.gmt_m1_target)
        self.large_target_list.target.add(self.gmt_m0_target)
        self.large_target_list.target.add(self.gmt_p1_target)
        self.large_target_list.target.add(self.gmt_p6_target)
        self.large_target_list.target.add(self.gmt_p7_target)
        self.large_target_list.target.add(self.gmt_p8_target)
        self.large_target_list.target.add(self.gmt_p9_target)
        self.large_target_list.target.add(self.gmt_p12_target)
        self.large_target_list.save()

        self.immediate_engagement = Engagement(
            name=u'Test Immediate Engagement',
            description=u'Test immediate engagement description: Capitestla One.',
            domain=self.testserver_domain,
            path=u'capitestla_one',
            schedule=self.schedule_one,
            email_server=self.email_server,
            email_template=self.email_template,
            landing_page=self.landing_page,
            redirect_page=self.redirect_page,
            campaign=self.campaign,
            state=0,
            start_type='immediate',
            start_date=None,
            start_time=None
        )
        self.immediate_engagement.save()
        self.immediate_engagement.target_lists.add(self.target_list)

        self.countdown_delta = dj_tz.timedelta(seconds=900)
        # This datetime.datetime is only needed to add the countdown delta
        # to the instance attribute countdown_start_time.
        _countdown_start_datetime = datetime.datetime(
            year=1900, month=1, day=1,
            hour=0, minute=0, second=0
        )
        _countdown_start_datetime += self.countdown_delta
        self.countdown_start_time = datetime.time(
            hour=_countdown_start_datetime.hour,
            minute=_countdown_start_datetime.minute,
            second=_countdown_start_datetime.second
        )

        self.countdown_engagement = Engagement(
            name=u'Test Countdown Engagement',
            description=u'Test countdown engagement description: Capitestla Two.',
            domain=self.testserver_domain,
            path=u'capitestla_two',
            schedule=self.schedule_one,
            email_server=self.email_server,
            email_template=self.email_template,
            landing_page=self.landing_page,
            redirect_page=self.redirect_page,
            campaign=self.campaign,
            state=0,
            start_type='countdown',
            start_date=None,
            start_time=self.countdown_start_time
        )
        self.countdown_engagement.save()
        self.countdown_engagement.target_lists.add(self.target_list)

        # This ensures tests involving specific_date sending_types will always
        # have a future date to check against.
        self.specific_date_start_datetime = self.now + dj_tz.timedelta(days=1, hours=1)
        self.specific_date_start_date = datetime.date(
            year=self.specific_date_start_datetime.year,
            month=self.specific_date_start_datetime.month,
            day=self.specific_date_start_datetime.day
        )
        self.specific_date_start_time = datetime.time(
            hour=self.specific_date_start_datetime.hour,
            minute=self.specific_date_start_datetime.minute,
            second=self.specific_date_start_datetime.second
        )

        self.specific_date_engagement = Engagement(
            name=u'Test Specifc Date Engagement',
            description=u'Test engagement description: TestBook.',
            domain=self.testserver_domain,
            path=u'testbook',
            schedule=self.schedule_two,
            email_server=self.email_server,
            email_template=self.email_template,
            landing_page=self.landing_page,
            redirect_page=self.redirect_page,
            campaign=self.campaign,
            state=0,
            start_type='specific_date',
            start_date=self.specific_date_start_date,
            start_time=self.specific_date_start_time
        )
        self.specific_date_engagement.save()
        self.specific_date_engagement.target_lists.add(self.large_target_list)

    def make_timezone_target(self, tz):
        name = tz.lower().replace('-', 'm').replace('+', 'p').replace('/', '')
        return Target(email=name + '@gmail.com',
                      firstname=name + '_f',
                      lastname=name + '_l',
                      timezone=tz)


class TestViews(SandbarTest):

    def test_incorrect_hostname(self):
        """ Hostname mismatches should always return 404s. """

        # Non-user attempts to visit https://badhost/clients/list
        # Note that this first case does not require `follow` because the
        # non-user does not trigger an attempted redirect to the login page
        # before the middleware denies it. Any potential 302 attempted with a
        # hostname that does not match Sandbar's HOST settting should
        # immediately and only return a 404 instead of a 302.
        e404 = self.app.get(
            'https://badhost/clients/list/',
            user=None,
            headers={'HOST': 'badhost'},
            expect_errors=True
        )
        self.assertEqual(e404.status_code, 404)

        # Non-staff user attempts to visit https://badhost/clients/list
        e404 = self.app.get(
            'https://badhost/clients/list/',
            user='nonstaff.user',
            headers={'HOST': 'badhost'},
            expect_errors=True
        )
        self.assertEqual(e404.status_code, 404)

        # Staff user attempts to visit https://badhost/clients/list
        e404 = self.app.get(
            'https://badhost/clients/list/',
            user='staff.user',
            headers={'HOST': 'badhost'},
            expect_errors=True
        )
        self.assertEqual(e404.status_code, 404)

        # Superuser attempts to visit https://badhost/clients/list
        e404 = self.app.get(
            'https://badhost/clients/list/',
            user='super.user',
            headers={'HOST': 'badhost'},
            expect_errors=True
        )
        self.assertEqual(e404.status_code, 404)

    def test_pathless_sandbar_hostname(self):
        e404 = self.app.get(
            'https://testserver/',
            user=None,
            status='404 NOT FOUND',
            headers={'HOST': 'testserver'}
        )
        self.assertEqual(e404.request.url, 'https://testserver/')

        self.assertContains(e404, 'Not Found', status_code=404)
        self.assertEqual(e404.request.url, 'https://testserver/')
        # This isn't necessary; I'm leaving it in to be explicit...
        self.assertEqual(e404.status_code, 404)
        # ... and to demonstrate its difference from this:
        self.assertEqual(e404.status, '404 NOT FOUND')

        e404 = self.app.get(
            'https://testserver/',
            user='nonstaff.user',
            status='404 NOT FOUND',
            headers={'HOST': 'testserver'}
        )
        self.assertEqual(e404.request.url, 'https://testserver/')
        self.assertContains(e404, 'Not Found', status_code=404)
        self.assertEqual(e404.status_code, 404)
        self.assertEqual(e404.status, '404 NOT FOUND')

        e404 = self.app.get(
            'https://testserver/',
            user='staff.user',
            status='404 NOT FOUND',
            headers={'HOST': 'testserver'}
        )
        self.assertEqual(e404.request.url, 'https://testserver/')
        self.assertContains(e404, 'Not Found', status_code=404)
        self.assertEqual(e404.status_code, 404)
        self.assertEqual(e404.status, '404 NOT FOUND')

        e404 = self.app.get(
            'https://testserver/',
            user='super.user',
            status='404 NOT FOUND',
            headers={'HOST': 'testserver'}
        )
        self.assertEqual(e404.request.url, 'https://testserver/')
        self.assertContains(e404, 'Not Found', status_code=404)
        self.assertEqual(e404.status_code, 404)
        self.assertEqual(e404.status, '404 NOT FOUND')

    def test_clientsList(self):
        # Redirects to login for null user.
        clientsList = self.app.get('https://testserver/clients/list/',
            user=None,
            headers={'HOST': 'testserver'}
        )
        self.assertEqual(clientsList.status_code, 302)

        # Here's a bunch of asserts that are handy to be aware of when writing
        # tests that rely on distinguishing between specific parts of URLs.
        self.assertEqual(
            clientsList.request.url, 'https://testserver/clients/list/'
        )
        # The WebTest client's request server.
        # Only identical to host server due to being a test.
        self.assertEqual(
            clientsList.request.application_url, 'https://testserver'
        )
        # The test client's host server.
        # The counterpart to request.application_url -- identical due to test.
        self.assertEqual(clientsList.request.host_url, 'https://testserver')
        self.assertEqual(clientsList.request.domain, 'testserver')
        self.assertEqual(clientsList.request.host, 'testserver')
        self.assertEqual(clientsList.request.host_port, '443')
        self.assertEqual(clientsList.request.remote_addr, '127.0.0.1')
        self.assertEqual(clientsList.request.path, '/clients/list/')
        self.assertEqual(
            clientsList.url,
            'https://testserver/accounts/login/?next=/clients/list/'
        )

        login_page = clientsList.follow(headers={'HOST': 'testserver'})
        self.assertEqual(login_page.status_code, 200)
        self.assertNotContains(
            login_page,
            '<a title="Add Client" href="/clients/add/">Add Client</a>'
        )

        clientsList = self.app.get(
            'https://testserver/clients/list/',
            user='nonstaff.user',
            headers={'HOST': 'testserver'}
        )
        self.assertContains(
            clientsList,
            '<a title="Add Client" href="/clients/add/">Add Client</a>'
        )
        clientsList = self.app.get(
            'https://testserver/clients/list/',
            user='staff.user',
            headers={'HOST': 'testserver'}
        )
        self.assertContains(
            clientsList,
            '<a title="Add Client" href="/clients/add/">Add Client</a>'
        )
        clientsList = self.app.get(
            'https://testserver/clients/list/',
            user='super.user',
            headers={'HOST': 'testserver'}
        )
        self.assertContains(
            clientsList,
            '<a title="Add Client" href="/clients/add/">Add Client</a>'
        )

    def test_save_response(self):
        # client.helpers.record_result_event, called by the ShowLandingPage
        # middleware, requires a VectorEmail to record a ResultEvent before it
        # is allowed to return a rendered LandingPage.
        # This is not in the setUp fixtures to isolate test data so that other
        # tests can require self.target_1 to not have a VectorEmail by default.
        # To ensure that ResultEvents are not being attributed to incorrect
        # Targets, these tests should check at least two Targets without
        # clearing the database.
        vemail = VectorEmail(engagement=self.immediate_engagement,
                             target=self.target_1)
        vemail.save()
        vemail_2 = VectorEmail(engagement=self.immediate_engagement,
                               target=self.target_2)
        vemail_2.save()

        ref_1 = self.target_1.encrypt_id(self.immediate_engagement.url_key)
        landing_page_get_url = '/{}/capitestla_one'.format(ref_1)
        landing_page = self.app.get(landing_page_get_url,
                                    user=None,
                                    # 'HTTP_' is prepended by WebTest.
                                    headers={'USER_AGENT': 'Mozilla/5.0',
                                             'HOST': 'testserver'})
        self.assertEqual(landing_page.status_code, 200)
        self.assertContains(landing_page, 'This was a landing page test')
        self.assertContains(landing_page, "SB&nbsp;Password")
        self.assertContains(landing_page, "SB&nbsp;Login")

        landing_page.form['sb_login'].value = u'SB Login Test 1'
        landing_page.form['sb_password'].value = u'SB Password Test 1'
        redirect_page = landing_page.form.submit(
            headers={'USER_AGENT': 'Mozilla/5.0', 'HOST': 'testserver'}
        )
        self.assertEqual(redirect_page.status_code, 200)
        self.assertContains(redirect_page, 'This was a redirect page test')

        # This should return exactly one VectorEmail.
        submit_result_1 = vemail.result_event.get(
            vector_email__target=self.target_1,
            event_type=ResultEvent.SUBMIT
        )
        expected_saved_submit_data = ['"sb_login": "SB Login Test 1"',
                                      '"sb_password": "SB Password Test 1"']
        for expected in expected_saved_submit_data:
            # WebTest forces its assertContains method to check status codes.
            # Here's a workaround that favors rapid debugging:
            assert submit_result_1.raw_data.count(expected) == 1, \
                ('\nSaved submit data missing:\n    {}\n'
                 'Actual saved submit data: \n    {}'
                 ''.format(expected, submit_result_1.raw_data))

        # Creating and checking ResultEvents for the second Target.
        ref_2 = self.target_2.encrypt_id(self.immediate_engagement.url_key)
        self.assertNotEqual(Target.decrypt_id(self.immediate_engagement.url_key, ref_1),
                            Target.decrypt_id(self.immediate_engagement.url_key, ref_2))
        landing_page_get_url = '/{}/capitestla_one'.format(ref_2)
        landing_page = self.app.get(landing_page_get_url,
                                    user=None,
                                    headers={'USER_AGENT': 'Mozilla/5.0',
                                             'HOST': 'testserver'})
        self.assertEqual(landing_page.status_code, 200)
        self.assertContains(landing_page, 'This was a landing page test')
        self.assertContains(landing_page, "SB&nbsp;Password")
        self.assertContains(landing_page, "SB&nbsp;Login")

        landing_page.form['sb_login'].value = u'SB Login Test 2'
        landing_page.form['sb_password'].value = u'SB Password Test 2'
        redirect_page = landing_page.form.submit(
            headers={'USER_AGENT': 'Mozilla/5.0', 'HOST': 'testserver'}
        )
        self.assertEqual(redirect_page.status_code, 200)
        self.assertContains(redirect_page, 'This was a redirect page test')

        # Check for incorrect Target attribution by seeing if more than one
        # ResultEvent was created for the first Target in the Engagement:
        vemail.result_event.get(
            vector_email__target=self.target_1,
            event_type=ResultEvent.SUBMIT
        )

        # This should return exactly one VectorEmail.
        submit_result_2 = vemail_2.result_event.get(
            vector_email__target=self.target_2,
            event_type=ResultEvent.SUBMIT
        )
        self.assertNotEqual(submit_result_1.vector_email.get().target.id,
                            submit_result_2.vector_email.get().target.id)
        expected_saved_submit_data = ['"sb_login": "SB Login Test 2"',
                                      '"sb_password": "SB Password Test 2"']
        for expected in expected_saved_submit_data:
            # WebTest forces its assertContains method to check status codes.
            # Here's a workaround that favors rapid debugging:
            assert submit_result_2.raw_data.count(expected) == 1, \
                ('\nSaved submit data missing:\n    {}\n'
                 'Actual saved submit data: \n    {}'
                 ''.format(expected, submit_result_2.raw_data))

    def test_emailTemplateEdit(self):
        emailTemplateEdit = self.app.get(
            'https://testserver/email-templates/add/',
            user='staff.user',
            headers={'HOST': 'testserver'}
        )
        emailTemplateEdit.form.fields['name'][0].value = 'Test Template'
        emailTemplateEdit.form.fields['from_header'][0].value = 'Test Emailers'
        emailTemplateEdit.form.fields['subject_header'][0].value = 'Test Sale!'
        emailTemplateEdit.form.fields['template'][0].value = 'http://[#[url]#]'
        result = emailTemplateEdit.form.submit(headers={'HOST': 'testserver'})\
                                       .follow(headers={'HOST': 'testserver'})
        self.assertEqual(result.status_code, 200)
        self.assertContains(result, 'Test Template')
        self.assertEqual(
            result.request.url,
            'https://testserver/email-templates/list/'
        )

        test_email = EmailTemplate.objects.get(name__contains='Test Template')
        self.assertEqual(test_email.name, 'Test Template')
        self.assertEqual(test_email.from_header, 'Test Emailers')
        self.assertEqual(test_email.subject_header, 'Test Sale!')
        # The view should remove the "http://", because "[#[url]#]" will add it
        # when the EmailTemplate is filled during client.tasks.generateContent.
        self.assertEqual(test_email.template, '[#[url]#]')

    def test_emailServerEdit(self):
        emailServerEdit = self.app.get(
            'https://testserver/email-servers/add/',
            user='staff.user',
            headers={'HOST': 'testserver'}
        )
        emailServerEdit.form.fields['host'][0].value = 'pretend.smtp.relay'
        emailServerEdit.form.fields['port'][0].value = '999'
        emailServerEdit.form.fields['use_tls'][0].value = True
        emailServerEdit.form.fields['login'][0].value = 'test@test.com'
        emailServerEdit.form.fields['email_pw'][0].value = 'XXXXXXXXXXXXXXXX'
        result = emailServerEdit.form.submit(headers={'HOST': 'testserver'})\
                                     .follow(headers={'HOST': 'testserver'})
        self.assertEqual(result.status_code, 200)
        self.assertContains(result, 'test@test.com')
        self.assertEqual(
            result.request.url,
            'https://testserver/email-servers/list/'
        )

        test_server = EmailServer.objects.get(login='test@test.com')
        self.assertEqual(test_server.host, 'pretend.smtp.relay')
        self.assertEqual(test_server.port, 999)
        self.assertEqual(test_server.use_tls, True)
        self.assertEqual(test_server.login, 'test@test.com')
        # Note that EmailServer's field is `password`, not `email_pw`:
        self.assertEqual(test_server.password, 'XXXXXXXXXXXXXXXX')
        self.assertEqual(test_server.test_recipient,
                         'info@rhinosecuritylabs.com')


class TestModels(SandbarTest):

    def test_model_creation(self):
        self.assertEqual(PhishingDomain.objects.count(), 1)
        self.assertEqual(ScraperUserAgent.objects.count(), 1)
        self.assertEqual(LandingPage.objects.count(), 2)  # incl redirects
        self.assertEqual(Client.objects.count(), 1)
        self.assertEqual(Campaign.objects.count(), 1)
        self.assertEqual(Schedule.objects.count(), 4)
        self.assertEqual(ScheduleWindow.objects.count(), 1)
        self.assertEqual(EmailServer.objects.count(), 1)
        self.assertEqual(EmailTemplate.objects.count(), 1)
        self.assertEqual(Target.objects.count(), 13)
        self.assertEqual(TargetList.objects.count(), 2)
        self.assertEqual(self.target_list.target.count(), 2)
        self.assertEqual(self.large_target_list.target.count(), 11)
        self.assertEqual(Engagement.objects.count(), 3)
        self.assertEqual(VectorEmail.objects.count(), 0)
        self.assertEqual(ResultEvent.objects.count(), 0)

    def test_engagement_initialization(self):
        self.assertEqual(VectorEmail.objects.count(), 0)
        self.assertTrue(self.immediate_engagement.url_key is not None)
        self.assertEqual(self.immediate_engagement.state, 0)
        self.assertEqual(self.immediate_engagement.get_state_display(), 'Not Launched')
        self.assertEqual(self.immediate_engagement.status, (0, '0/0', (None, None)))
        self.assertEqual(self.immediate_engagement.get_result_statistics(),
                         (0, (0, '0%'), (0, '0%'), (0, '0%')))
        self.assertEqual(self.immediate_engagement.target_lists.count(), 1)

        self.immediate_engagement.create_vector_emails()
        self.assertTrue(self.immediate_engagement.url_key is not None)
        self.assertEqual(self.immediate_engagement.state, 0)
        self.assertEqual(self.immediate_engagement.get_state_display(), 'Not Launched')
        self.assertEqual(VectorEmail.objects.count(), 2)
        self.assertEqual(self.immediate_engagement.status, (0, '0/2', (None, None)))
        self.assertEqual(self.immediate_engagement.get_result_statistics(),
                         (2, (0, '0%'), (0, '0%'), (0, '0%')))
        self.assertEqual(self.immediate_engagement.target_lists.count(), 1)

    def test_site_settings_singleton_constraint(self):
        self.assertEqual(SiteSettings.load().id, 1)
        self.assertEqual(SiteSettings.objects.count(), 1)

        SiteSettings.objects.get().delete()
        self.assertEqual(SiteSettings.objects.count(), 1)

        new_site_settings = SiteSettings()
        with self.assertRaises(IntegrityError):
            new_site_settings.save()


class TestImmediateEngagements(SandbarTest):

    def test_effect_of_immediate_engagement_toggling_on_v_e_send_ats(self):
        self.immediate_engagement.create_vector_emails()

        start_result = self.immediate_engagement._start_engagement('start')
        self.assertEqual(start_result, 'Success')

        cumulative_interval = self.immediate_engagement.schedule.interval * self.immediate_engagement.vector_email.count()
        cumulative_delta = dj_tz.timedelta(seconds=cumulative_interval)
        lower_bound = self.now - dj_tz.timedelta(seconds=1)
        upper_bound = self.now + cumulative_delta

        for vector_email in self.immediate_engagement.vector_email.all():
            self.assertEqual(vector_email.state, VectorEmail.READY)
            self.assertTrue(vector_email.send_at <= upper_bound)
            self.assertTrue(vector_email.send_at >= lower_bound)

        self.immediate_engagement._pause_engagement()

        for vector_email in self.immediate_engagement.vector_email.all():
            self.assertEqual(vector_email.state, VectorEmail.PAUSED)
            self.assertEqual(vector_email.send_at, None)

        unpause_result = self.immediate_engagement._start_engagement('unpause')
        self.assertEqual(unpause_result, 'Success')

        for vector_email in self.immediate_engagement.vector_email.all():
            self.assertEqual(vector_email.state, VectorEmail.READY)
            self.assertTrue(vector_email.send_at <= upper_bound)
            self.assertTrue(vector_email.send_at >= lower_bound)


class TestCountdownEngagements(SandbarTest):

    def test_effect_of_countdown_engagement_toggling_on_v_e_send_ats(self):
        self.countdown_engagement.create_vector_emails()

        start_result = self.countdown_engagement._start_engagement('start')
        self.assertEqual(start_result, 'Success')

        cumulative_interval = self.countdown_engagement.schedule.interval * self.countdown_engagement.vector_email.count()
        cumulative_delta = dj_tz.timedelta(seconds=cumulative_interval)
        lower_bound = self.now - dj_tz.timedelta(seconds=1) + self.countdown_delta
        upper_bound = self.now + cumulative_delta + self.countdown_delta

        for vector_email in self.countdown_engagement.vector_email.all():
            self.assertEqual(vector_email.state, VectorEmail.READY)
            self.assertTrue(vector_email.send_at <= upper_bound)
            self.assertTrue(vector_email.send_at >= lower_bound)

        self.countdown_engagement._pause_engagement()

        for vector_email in self.countdown_engagement.vector_email.all():
            self.assertEqual(vector_email.state, VectorEmail.PAUSED)
            self.assertEqual(vector_email.send_at, None)

        unpause_result = self.countdown_engagement._start_engagement('unpause')
        self.assertEqual(unpause_result, 'Success')

        for vector_email in self.countdown_engagement.vector_email.all():
            self.assertEqual(vector_email.state, VectorEmail.READY)
            self.assertTrue(vector_email.send_at <= upper_bound)
            self.assertTrue(vector_email.send_at >= lower_bound)


class TestSpecificDateEngagements(SandbarTest):

    def test_create_vector_emails_with_send_type_specific_date(self):
        self.assertEqual(self.large_target_list.target.count(), 11)
        self.assertEqual(VectorEmail.objects.count(), 0)

        self.specific_date_engagement.create_vector_emails()

        self.assertEqual(self.large_target_list.target.count(), 11)
        self.assertEqual(VectorEmail.objects.count(), 11)
        unscheduled_vemails_in_engagement = VectorEmail.objects.filter(
            engagement=self.specific_date_engagement,
            state=VectorEmail.UNSCHEDULED
        )
        self.assertEqual(unscheduled_vemails_in_engagement.count(), 11)

        self.specific_date_engagement.schedule_vector_emails(
            states_to_reschedule=[VectorEmail.UNSCHEDULED]
        )

        vemails_with_null_send_ats_in_engagement = VectorEmail.objects.\
            filter(engagement=self.specific_date_engagement,
                   send_at__isnull=True)
        self.assertEqual(vemails_with_null_send_ats_in_engagement.count(), 0)

        unscheduled_vemails_in_engagement = VectorEmail.objects.\
            filter(engagement=self.specific_date_engagement,
                   state=VectorEmail.UNSCHEDULED)
        self.assertEqual(unscheduled_vemails_in_engagement.count(), 11)

        ready_vemails_in_engagement = VectorEmail.objects.\
            filter(engagement=self.specific_date_engagement, state=VectorEmail.READY)
        self.assertEqual(ready_vemails_in_engagement.count(), 0)

        sent_vemails_in_engagement = VectorEmail.objects.\
            filter(engagement=self.specific_date_engagement, state=VectorEmail.SENT)
        self.assertEqual(sent_vemails_in_engagement.count(), 0)

        send_missed_vemails_in_engagement = VectorEmail.objects.\
           filter(engagement=self.specific_date_engagement, state=VectorEmail.SEND_MISSED)
        self.assertEqual(send_missed_vemails_in_engagement.count(), 0)

    def test__start_engagement_with_send_type_specific_date(self):
        self.assertEqual(self.large_target_list.target.count(), 11)
        self.assertEqual(VectorEmail.objects.count(), 0)

        self.specific_date_engagement.create_vector_emails()

        self.assertEqual(self.large_target_list.target.count(), 11)
        self.assertEqual(VectorEmail.objects.count(), 11)

        start_result = self.specific_date_engagement._start_engagement('start')
        self.assertEqual(start_result, 'Success')

        vemails_with_null_send_ats_in_engagement = VectorEmail.objects.\
            filter(engagement=self.specific_date_engagement,
                   send_at__isnull=True)
        self.assertEqual(vemails_with_null_send_ats_in_engagement.count(), 0)

        unscheduled_vemails_in_engagement = VectorEmail.objects.\
            filter(engagement=self.specific_date_engagement,
                   state=VectorEmail.UNSCHEDULED)
        self.assertEqual(unscheduled_vemails_in_engagement.count(), 0)

        ready_vemails_in_engagement = VectorEmail.objects.\
            filter(engagement=self.specific_date_engagement, state=VectorEmail.READY)
        self.assertEqual(ready_vemails_in_engagement.count(), 11)

        sent_vemails_in_engagement = VectorEmail.objects.\
            filter(engagement=self.specific_date_engagement, state=VectorEmail.SENT)
        self.assertEqual(sent_vemails_in_engagement.count(), 0)

        send_missed_vemails_in_engagement = VectorEmail.objects.\
           filter(engagement=self.specific_date_engagement, state=VectorEmail.SEND_MISSED)
        self.assertEqual(send_missed_vemails_in_engagement.count(), 0)

    def test_effect_of_specific_date_engagement_toggling_on_v_e_send_ats(self):
        self.specific_date_engagement.create_vector_emails()

        start_result = self.specific_date_engagement._start_engagement('start')
        self.assertEqual(start_result, 'Success')

        cumulative_interval = self.specific_date_engagement.schedule.interval * self.specific_date_engagement.vector_email.count()
        cumulative_delta = dj_tz.timedelta(seconds=cumulative_interval)
        lower_bound = self.specific_date_start_datetime - dj_tz.timedelta(seconds=1)
        upper_bound = self.specific_date_start_datetime + cumulative_delta

        for vector_email in self.specific_date_engagement.vector_email.all():
            self.assertEqual(vector_email.state, VectorEmail.READY)
            self.assertTrue(vector_email.send_at <= upper_bound)
            self.assertTrue(vector_email.send_at >= lower_bound)

        self.specific_date_engagement._pause_engagement()

        for vector_email in self.specific_date_engagement.vector_email.all():
            self.assertEqual(vector_email.state, VectorEmail.PAUSED)
            self.assertEqual(vector_email.send_at, None)

        unpause_result = self.specific_date_engagement._start_engagement('unpause')
        self.assertEqual(unpause_result, 'Success')

        for vector_email in self.specific_date_engagement.vector_email.all():
            self.assertEqual(vector_email.state, VectorEmail.READY)
            self.assertTrue(vector_email.send_at <= upper_bound)
            self.assertTrue(vector_email.send_at >= lower_bound)


class TestScheduling(SandbarTest):

    def test_weekdaily_and_hourly_schedule_windows(self):
        self.immediate_engagement.schedule = self.schedule_with_schedule_window
        self.immediate_engagement.save()
        self.immediate_engagement.create_vector_emails()

        start_result = self.immediate_engagement._start_engagement('start')
        self.assertEqual(start_result, 'Success', self.immediate_engagement.internal_error)

        cumulative_interval = self.immediate_engagement.schedule.interval * self.immediate_engagement.vector_email.count()
        cumulative_delta = dj_tz.timedelta(seconds=cumulative_interval)

        # Scheduling may place the first email anywhere in the first minute
        # permitted by the earliest ScheduleWindow.
        lower_bound = self.three_datetime_hours_from_the_datetime_after_tomorrow - dj_tz.timedelta(seconds=60)
        upper_bound = self.six_datetime_hours_from_the_datetime_after_tomorrow + cumulative_delta

        for vector_email in self.immediate_engagement.vector_email.all():
            self.assertEqual(vector_email.state, VectorEmail.READY)
            self.assertTrue(vector_email.send_at <= upper_bound)
            self.assertTrue(vector_email.send_at >= lower_bound)

        self.immediate_engagement._pause_engagement()

        for vector_email in self.immediate_engagement.vector_email.all():
            self.assertEqual(vector_email.state, VectorEmail.PAUSED)
            self.assertEqual(vector_email.send_at, None)

        unpause_result = self.immediate_engagement._start_engagement('unpause')
        self.assertEqual(unpause_result, 'Success', self.immediate_engagement.internal_error)

        for vector_email in self.immediate_engagement.vector_email.all():
            self.assertEqual(vector_email.state, VectorEmail.READY)
            self.assertTrue(vector_email.send_at <= upper_bound)
            self.assertTrue(vector_email.send_at >= lower_bound)

    def test_excluded_dates_with_immediate_engagements(self):
        self.immediate_engagement.schedule = self.schedule_with_excluded_dates
        self.immediate_engagement.save()
        self.immediate_engagement.create_vector_emails()

        start_result = self.immediate_engagement._start_engagement('start')
        self.assertEqual(start_result, 'Success')

        cumulative_interval = self.immediate_engagement.schedule.interval * self.immediate_engagement.vector_email.count()
        cumulative_delta = dj_tz.timedelta(seconds=cumulative_interval)

        # Because we're using excluded_dates with no ScheduleWindows specifying
        # acceptable sending times, the scheduled times will occur at UTC
        # mightnight of the day after tomorrow.
        # These are "dates" because they aren't being given any hour, minute,
        # or second values, but they need to remain datetimes so that
        # dj_tz.timedelta can be used on them (to handle rollover increments).
        the_naive_date_after_tomorrow = dj_tz.datetime(
            year=self.the_datetime_after_tomorrow.year,
            month=self.the_datetime_after_tomorrow.month,
            day=self.the_datetime_after_tomorrow.day
        )
        server_timezone = dj_tz.get_default_timezone()
        the_date_after_tomorrow = server_timezone.localize(the_naive_date_after_tomorrow)

        lower_bound = the_date_after_tomorrow - dj_tz.timedelta(seconds=1)
        upper_bound = the_date_after_tomorrow + cumulative_delta

        for vector_email in self.immediate_engagement.vector_email.all():
            self.assertEqual(vector_email.state, VectorEmail.READY)
            self.assertTrue(vector_email.send_at <= upper_bound)
            self.assertTrue(vector_email.send_at >= lower_bound)

        self.immediate_engagement._pause_engagement()

        for vector_email in self.immediate_engagement.vector_email.all():
            self.assertEqual(vector_email.state, VectorEmail.PAUSED)
            self.assertEqual(vector_email.send_at, None)

        unpause_result = self.immediate_engagement._start_engagement('unpause')
        self.assertEqual(unpause_result, 'Success')

        for vector_email in self.immediate_engagement.vector_email.all():
            self.assertEqual(vector_email.state, VectorEmail.READY)
            self.assertTrue(vector_email.send_at <= upper_bound)
            self.assertTrue(vector_email.send_at >= lower_bound)

    def test_excluded_dates_with_specific_date_engagements(self):
        self.specific_date_engagement.schedule = self.schedule_with_excluded_dates
        self.specific_date_engagement.save()
        self.specific_date_engagement.create_vector_emails()

        start_result = self.specific_date_engagement._start_engagement('start')
        self.assertEqual(start_result, 'Success')

        cumulative_interval = self.specific_date_engagement.schedule.interval * self.specific_date_engagement.vector_email.count()
        cumulative_delta = dj_tz.timedelta(seconds=cumulative_interval)

        # Because we're using excluded_dates with no ScheduleWindows specifying
        # acceptable sending times, the scheduled times will occur at UTC
        # mightnight of the day after tomorrow.
        # These are "dates" because they aren't being given any hour, minute,
        # or second values, but they need to remain datetimes so that
        # dj_tz.timedelta can be used on them (to handle rollover increments).
        the_naive_date_after_tomorrow = dj_tz.datetime(
            year=self.the_datetime_after_tomorrow.year,
            month=self.the_datetime_after_tomorrow.month,
            day=self.the_datetime_after_tomorrow.day
        )
        server_timezone = dj_tz.get_default_timezone()
        the_date_after_tomorrow = server_timezone.localize(the_naive_date_after_tomorrow)

        lower_bound = the_date_after_tomorrow - dj_tz.timedelta(seconds=1)
        upper_bound = the_date_after_tomorrow + cumulative_delta

        for vector_email in self.specific_date_engagement.vector_email.all():
            self.assertEqual(vector_email.state, VectorEmail.READY)
            self.assertTrue(vector_email.send_at <= upper_bound)
            self.assertTrue(vector_email.send_at >= lower_bound)

        self.specific_date_engagement._pause_engagement()

        for vector_email in self.specific_date_engagement.vector_email.all():
            self.assertEqual(vector_email.state, VectorEmail.PAUSED)
            self.assertEqual(vector_email.send_at, None)

        unpause_result = self.specific_date_engagement._start_engagement('unpause')
        self.assertEqual(unpause_result, 'Success')

        for vector_email in self.specific_date_engagement.vector_email.all():
            self.assertEqual(vector_email.state, VectorEmail.READY)
            self.assertTrue(vector_email.send_at <= upper_bound)
            self.assertTrue(vector_email.send_at >= lower_bound)


class TestEngagementReportView(SandbarTest):

    def setUp(self, *args, **kwargs):
        results = super(TestEngagementReportView, self).setUp(*args, **kwargs)

        self.target_a = Target(email='test_a@rhinosecuritylabs.com', firstname='a_first', lastname='a_last')
        self.target_b = Target(email='test_b@rhinosecuritylabs.com', firstname='b_first', lastname='b_last')
        self.target_a.save()
        self.target_b.save()

        self.target_list_a = TargetList(nickname='target-list-a', client=self.client)
        self.target_list_b = TargetList(nickname='target-list-b', client=self.client)
        self.target_list_c = TargetList(nickname='target-list-c', client=self.client)
        self.target_list_a.save()
        self.target_list_b.save()
        self.target_list_c.save()

        self.target_list_a.target.add(self.target_a)
        self.target_list_a.target.add(self.target_b)
        self.target_list_b.target.add(self.target_b)
        self.target_list_c.target.add(self.target_a)
        self.target_list_a.save()
        self.target_list_b.save()
        self.target_list_c.save()

        self.engagement_one = Engagement(
            name=u'Test Engagement One',
            description=u'Test engagement description: one',
            domain=self.testserver_domain,
            path=u'test_engagement_one',
            schedule=self.schedule_one,
            email_server=self.email_server,
            email_template=self.email_template,
            landing_page=self.landing_page,
            redirect_page=self.redirect_page,
            campaign=self.campaign,
            state=0
        )
        self.engagement_one.save()
        self.engagement_one.target_lists.add(self.target_list_a)
        self.engagement_one.target_lists.add(self.target_list_b)
        self.engagement_one.save()

        self.engagement_two = Engagement(
            name=u'Test Engagement Two',
            description=u'Test engagement description: Two',
            domain=self.testserver_domain,
            path=u'test_engagement_two',
            schedule=self.schedule_one,
            email_server=self.email_server,
            email_template=self.email_template,
            landing_page=self.landing_page,
            redirect_page=self.redirect_page,
            campaign=self.campaign,
            state=0
        )
        self.engagement_two.save()
        self.engagement_two.target_lists.add(self.target_list_c)
        self.engagement_two.save()

        self.engagement_one.create_vector_emails()
        self.engagement_two.create_vector_emails()

        self.target_a_engagement_one_results = ResultEvent.objects.bulk_create([
            ResultEvent(event_type=ResultEvent.OPEN, timestamp=dj_tz.now(), userAgent='Test UserAgent for Target A, Engagement One - $Click$', ip='127.0.0.1'),
            ResultEvent(event_type=ResultEvent.CLICK, timestamp=dj_tz.now(), userAgent='Test UserAgent for Target A, Engagement One - $Open$', ip='127.0.0.1'),
            ResultEvent(event_type=ResultEvent.SUBMIT, timestamp=dj_tz.now(), userAgent='Test UserAgent for Target A, Engagement One - $Submit$', ip='127.0.0.1', login='TargetAEngagementOne', password='TargetAEngagementOne'),
        ])

        self.target_a_engagement_two_results = ResultEvent.objects.bulk_create([
            ResultEvent(event_type=ResultEvent.OPEN, timestamp=dj_tz.now(), userAgent='Test UserAgent for Target A, Engagement Two - $Open$', ip='127.0.0.1'),
            ResultEvent(event_type=ResultEvent.CLICK, timestamp=dj_tz.now(), userAgent='Test UserAgent for Target A, Engagement Two - $Click$', ip='127.0.0.1'),
            ResultEvent(event_type=ResultEvent.SUBMIT, timestamp=dj_tz.now(), userAgent='Test UserAgent for Target A, Engagement Two - $Submit$', ip='127.0.0.1', login='TargetAEngagementTwo', password='TargetAEngagementTwo'),
        ])

        self.target_b_engagement_one_results = ResultEvent.objects.bulk_create([
            ResultEvent(event_type=ResultEvent.OPEN, timestamp=dj_tz.now(), userAgent='Test UserAgent for Target B, Engagement One - $Click$', ip='127.0.0.1'),
            ResultEvent(event_type=ResultEvent.CLICK, timestamp=dj_tz.now(), userAgent='Test UserAgent for Target B, Engagement One - $Open$', ip='127.0.0.1'),
            ResultEvent(event_type=ResultEvent.SUBMIT, timestamp=dj_tz.now(), userAgent='Test UserAgent for Target B, Engagement One - $Submit$', ip='127.0.0.1', login='TargetBEngagementOne', password='TargetBEngagementOne'),
        ])

        for each_result in self.target_a_engagement_one_results + self.target_a_engagement_two_results + self.target_b_engagement_one_results:
            each_result.save()

        self.target_a_engagement_one_vector_email = self.engagement_one.vector_email.get(target__email__icontains='test_a')
        self.target_a_engagement_two_vector_email = self.engagement_two.vector_email.get(target__email__icontains='test_a')
        self.target_b_engagement_one_vector_email = self.engagement_one.vector_email.get(target__email__icontains='test_b')

        for each_result in self.target_a_engagement_one_results:
            self.target_a_engagement_one_vector_email.result_event.add(each_result)
        for each_result in self.target_a_engagement_two_results:
            self.target_a_engagement_two_vector_email.result_event.add(each_result)
        for each_result in self.target_b_engagement_one_results:
            self.target_b_engagement_one_vector_email.result_event.add(each_result)

        # Test that the database-only setup worked; has no relevance to views:
        self.assertEqual(VectorEmail.objects.filter(engagement=self.engagement_one).count(), 2)
        self.assertEqual(VectorEmail.objects.filter(engagement=self.engagement_two).count(), 1)
        self.assertEqual(ResultEvent.objects.filter(vector_email=self.target_a_engagement_one_vector_email).count(), 3)
        self.assertEqual(ResultEvent.objects.filter(vector_email=self.target_a_engagement_two_vector_email).count(), 3)
        self.assertEqual(ResultEvent.objects.filter(vector_email=self.target_b_engagement_one_vector_email).count(), 3)

        a_one_result_ids = set(ResultEvent.objects.filter(vector_email=self.target_a_engagement_one_vector_email).values_list('id', flat=True))
        a_two_result_ids = set(ResultEvent.objects.filter(vector_email=self.target_a_engagement_two_vector_email).values_list('id', flat=True))
        b_one_result_ids = set(ResultEvent.objects.filter(vector_email=self.target_b_engagement_one_vector_email).values_list('id', flat=True))

        self.assertNotEqual(a_one_result_ids, a_two_result_ids)
        self.assertNotEqual(a_one_result_ids, b_one_result_ids)
        self.assertNotEqual(a_two_result_ids, b_one_result_ids)

        return results

    def test_engagement_report_view(self):
        engagement_one_report = self.app.get(
            'https://testserver/engagements/report/{}/'.format(self.engagement_one.id),
            user='staff.user',
            headers={'HOST': 'testserver'}
        )

        for result_event in self.target_a_engagement_one_results:
            self.assertContains(engagement_one_report, result_event.userAgent)
        for result_event in self.target_a_engagement_two_results:
            self.assertNotContains(engagement_one_report, result_event.userAgent)
        for result_event in self.target_b_engagement_one_results:
            self.assertContains(engagement_one_report, result_event.userAgent)

        engagement_two_report = self.app.get(
            'https://testserver/engagements/report/{}/'.format(self.engagement_two.id),
            user='staff.user',
            headers={'HOST': 'testserver'}
        )

        for result_event in self.target_a_engagement_one_results:
            self.assertNotContains(engagement_two_report, result_event.userAgent)
        for result_event in self.target_a_engagement_two_results:
            self.assertContains(engagement_two_report, result_event.userAgent)
        for result_event in self.target_b_engagement_one_results:
            self.assertNotContains(engagement_two_report, result_event.userAgent)


class TestEncryption(SandbarTest):

    def test_encryption(self):

        encrypted = b64_encrypt(self.immediate_engagement.url_key,
                                str(self.target_1.id))
        self.assertNotEqual(encrypted, str(self.target_1.id))
        self.assertEqual(len(encrypted), 22)
        self.assertNotIn('=', encrypted)
        decrypted = b64_decrypt(self.immediate_engagement.url_key, encrypted)
        self.assertEqual(decrypted, str(self.target_1.id))


# # To use in the future. NYI
# class TestCSVParser(WebTest):
#    # ref:  http://codeinthehole.com/writing/
#    #              prefer-webtest-to-djangos-test-client-for-functional-tests/

# # This is only a guess from the online guide, not the actual function to use.
#     def test_upload_targets_from_csv(self):
#         index = self.app.get(
#             'https://testserver/target-lists/add/',
#             user='staff.user'
#         )

#         form = index.forms['csv_form']
#         content = ?????????
#         form['file'] = 'test_target_list.csv', content
#         form.submit(headers={'HOST': 'testserver'})

#         self.assertEqual('email here', target_list.targets.all()[0].email)
#         self.assertEqual('name', target_list.targets.all()[0].name)
