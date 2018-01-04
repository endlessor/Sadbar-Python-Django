from rest_framework_jwt.views import refresh_jwt_token
from dynamic_rest.routers import DynamicRouter
from django.conf.urls import url, include
from api import views

router = DynamicRouter()

router.register(r'site-settings', views.SiteSettingsViewSet)
router.register(r'slack-hooks', views.SlackHookViewSet)
router.register(r'users', views.UserViewSet)
router.register(r'profiles', views.ProfileViewSet)
router.register(r'email-servers', views.EmailServerViewSet)
router.register(r'phishing-domains', views.PhishingDomainViewSet)
router.register(r'scraper-user-agents', views.ScraperUserAgentViewSet)
router.register(r'schedules', views.ScheduleViewSet)
router.register(r'schedule-windows', views.ScheduleWindowViewSet)
router.register(r'landing-pages', views.LandingPageViewSet)
router.register(r'redirect-pages', views.RedirectPageViewSet)
router.register(r'email-templates', views.EmailTemplateViewSet)
router.register(r'clients', views.ClientViewSet)
router.register(r'campaigns', views.CampaignViewSet)
router.register(r'result-events', views.ResultEventViewSet)
router.register(r'target-data', views.TargetDatumViewSet)
router.register(r'targets', views.TargetViewSet)
router.register(r'target-lists', views.TargetListViewSet)
router.register(r'target-lists-flat-view', views.TargetListFlatViewSet)
router.register(r'vector-emails', views.VectorEmailViewSet)
router.register(r'engagements', views.EngagementViewSet)
router.register(r'oauth-engagements', views.OAuthEngagementViewSet)
router.register(r'oauth-consumers', views.OAuthConsumerViewSet)
router.register(r'oauth-results', views.OAuthResultViewSet)
router.register(r'plunder', views.PlunderViewSet)
router.register(r'shoalscrape-creds', views.ShoalScrapeCredsViewSet)
router.register(r'shoalscrape-tasks', views.ShoalScrapeTaskViewSet)
router.register(r'email-logs', views.EmailLogViewSet)
router.register(r'oauth-consoles', views.OAuthConsoleViewSet)
router.register(r'phishing-results', views.PhishingResultViewSet)


urlpatterns = [
    url(r'^landing-pages/preview/(?P<landing_page_id>\d+)/(?P<engagement_id>\d+)/(?P<target_id>\d+)',
        views.PreviewLandingPage.as_view()),
    url(r'^landing-pages/preview/(?P<landing_page_id>\d+)',
        views.PreviewLandingPage.as_view()),
    url(r'^vector-emails/(?P<vector_email_id>\d+)/email-preview',
        views.PreviewVectorEmailView.as_view()),

    url(r'^email-templates/shortcodes-check',
        views.CheckEmailTemplateShortcodes.as_view()),
    url(r'^email-servers/email-check',
        views.CheckEmailSettingsView.as_view()),
    url(r'^phishing-domains/domain-check',
        views.CheckPhishingDomainView.as_view()),

    url(r'^target-lists/csv-file', views.CSVUploadView.as_view()),

    url(r'^oauth-apis/google/gmail-messages/(?P<oa_result_id>\d+)/$',
        views.GmailMessagesView.as_view()),
    url(r'^oauth-apis/google/drive-files/(?P<oa_result_id>\d+)/$',
        views.DriveFilesView.as_view()),

    url(r'^token/$', views.CustomJSONWebTokenAPIView.as_view()),
    url(r'^token/refresh/$', refresh_jwt_token),

    url(r'^schema/$', views.schema_view),
    url(r'^', include(router.urls)),
]
