from rest_framework.test import APITestCase, APIClient

from django.core.urlresolvers import reverse

from api.utils import make_jwt_for_user
from client.models import LandingPage, Engagement
from client.tests import SandbarTest


class TestDeleteInProgressEngagementDependencyWarning(SandbarTest, APITestCase):

    def setUp(self, *args, **kwargs):
        result = super(TestDeleteInProgressEngagementDependencyWarning, self).setUp(*args, **kwargs)
        self.test_client = APIClient(enforce_csrf_checks=True, HTTP_HOST='testserver')
        return result

    def test_delete_landing_page_of_in_progress_engagement(self):
        detail_url = reverse('landing-pages-detail', kwargs={'version': 'v1', 'pk': self.landing_page.pk})

        self.immediate_engagement.state = Engagement.IN_PROGRESS
        self.immediate_engagement.save()

        auth_header = 'JWT {}'.format(make_jwt_for_user(self.staff_user))
        response = self.test_client.delete(detail_url, secure=True, format='json', HTTP_AUTHORIZATION=auth_header)
        self.assertEqual(response.status_code, 409)
        self.assertJSONEqual(response.content, {'dependent_engagements': [self.immediate_engagement.pk]})
        self.assertTrue(LandingPage.objects.filter(pk=self.landing_page.pk).exists())

    def test_delete_landing_page_of_paused_engagement(self):
        detail_url = reverse('landing-pages-detail', kwargs={'version': 'v1', 'pk': self.landing_page.pk})

        self.immediate_engagement.state = Engagement.PAUSED
        self.immediate_engagement.save()

        auth_header = 'JWT {}'.format(make_jwt_for_user(self.staff_user))
        response = self.test_client.delete(detail_url, secure=True, format='json', HTTP_AUTHORIZATION=auth_header)
        self.assertEqual(response.status_code, 204)
        self.assertFalse(LandingPage.objects.filter(pk=self.landing_page.pk).exists())


class TestDeleteInProgressEngagementWarning(SandbarTest, APITestCase):

    def setUp(self, *args, **kwargs):
        result = super(TestDeleteInProgressEngagementWarning, self).setUp(*args, **kwargs)
        self.test_client = APIClient(enforce_csrf_checks=True, HTTP_HOST='testserver')
        return result

    def test_delete_in_progress_engagement(self):
        detail_url = reverse('engagements-detail', kwargs={'version': 'v1', 'pk': self.immediate_engagement.pk})

        self.immediate_engagement.state = Engagement.IN_PROGRESS
        self.immediate_engagement.save()

        auth_header = 'JWT {}'.format(make_jwt_for_user(self.staff_user))
        response = self.test_client.delete(detail_url, secure=True, format='json', HTTP_AUTHORIZATION=auth_header)
        self.assertEqual(response.status_code, 409)
        self.assertJSONEqual(response.content, {'non_field_errors': 'Engagement {} is in progress and may not be deleted.'.format(self.immediate_engagement.pk)})
        self.assertTrue(Engagement.objects.filter(pk=self.immediate_engagement.pk).exists())

    def test_delete_paused_engagement(self):
        detail_url = reverse('engagements-detail', kwargs={'version': 'v1', 'pk': self.immediate_engagement.pk})

        self.immediate_engagement.state = Engagement.PAUSED
        self.immediate_engagement.save()

        auth_header = 'JWT {}'.format(make_jwt_for_user(self.staff_user))
        response = self.test_client.delete(detail_url, secure=True, format='json', HTTP_AUTHORIZATION=auth_header)
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Engagement.objects.filter(pk=self.immediate_engagement.pk).exists())


class TestPatchEngagementWithStateChange(SandbarTest, APITestCase):

    def setUp(self, *args, **kwargs):
        result = super(TestPatchEngagementWithStateChange, self).setUp(*args, **kwargs)
        self.test_client = APIClient(enforce_csrf_checks=True, HTTP_HOST='testserver')
        return result

    def test_start_engagement(self):
        detail_url = reverse('engagements-detail', kwargs={'version': 'v1', 'pk': self.immediate_engagement.pk})

        self.immediate_engagement.create_vector_emails()

        self.immediate_engagement.state = Engagement.NOT_LAUNCHED
        self.immediate_engagement.save()

        auth_header = 'JWT {}'.format(make_jwt_for_user(self.staff_user))
        response = self.test_client.patch(detail_url, {'commit': True, 'state': 1}, secure=True, format='json', HTTP_AUTHORIZATION=auth_header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Engagement.objects.get(pk=self.immediate_engagement.pk).state, 1)

    def test_start_engagement_with_description_change(self):
        detail_url = reverse('engagements-detail', kwargs={'version': 'v1', 'pk': self.immediate_engagement.pk})

        self.immediate_engagement.create_vector_emails()

        self.immediate_engagement.state = Engagement.NOT_LAUNCHED
        self.immediate_engagement.description = 'A'
        self.immediate_engagement.save()

        auth_header = 'JWT {}'.format(make_jwt_for_user(self.staff_user))
        response = self.test_client.patch(detail_url, {'commit': True, 'state': 1, 'description': 'B'}, secure=True, format='json', HTTP_AUTHORIZATION=auth_header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Engagement.objects.get(pk=self.immediate_engagement.pk).state, 1)
        self.assertEqual(Engagement.objects.get(pk=self.immediate_engagement.pk).description, 'A')

    def test_patch_unchanged_engagement_state_with_description_change(self):
        detail_url = reverse('engagements-detail', kwargs={'version': 'v1', 'pk': self.immediate_engagement.pk})

        self.immediate_engagement.state = Engagement.NOT_LAUNCHED
        self.immediate_engagement.description = 'A'
        self.immediate_engagement.save()

        auth_header = 'JWT {}'.format(make_jwt_for_user(self.staff_user))
        response = self.test_client.patch(detail_url, {'commit': True, 'state': 0, 'description': 'B'}, secure=True, format='json', HTTP_AUTHORIZATION=auth_header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Engagement.objects.get(pk=self.immediate_engagement.pk).state, 0)
        self.assertEqual(Engagement.objects.get(pk=self.immediate_engagement.pk).description, 'B')


class TestEngagementMissingDependenciesWarning(SandbarTest, APITestCase):

    def setUp(self, *args, **kwargs):
        result = super(TestEngagementMissingDependenciesWarning, self).setUp(*args, **kwargs)
        self.test_client = APIClient(enforce_csrf_checks=True, HTTP_HOST='testserver')
        return result

    def test_start_engagement_with_missing_email_server(self):
        detail_url = reverse('engagements-detail', kwargs={'version': 'v1', 'pk': self.immediate_engagement.pk})

        self.immediate_engagement.state = Engagement.NOT_LAUNCHED
        self.immediate_engagement.email_server = None
        self.immediate_engagement.save()

        auth_header = 'JWT {}'.format(make_jwt_for_user(self.staff_user))
        response = self.test_client.patch(detail_url, {'commit': True, 'state': 1}, secure=True, format='json', HTTP_AUTHORIZATION=auth_header)
        self.assertEqual(response.status_code, 424)
        self.assertEqual(Engagement.objects.get(pk=self.immediate_engagement.pk).state, 0)
        self.assertJSONEqual(response.content, {'non_field_errors': {'missing_dependencies': ['email_server']}})
