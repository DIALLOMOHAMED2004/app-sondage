from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from .models import Survey, Question, Choice, Response, Answer

class SurveyModelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.survey = Survey.objects.create(
            title='Test Survey',
            description='Test Description',
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=7),
            creator=self.user,
            status='draft'
        )
        self.question = Question.objects.create(
            survey=self.survey,
            text='Test Question',
            question_type='single',
            required=True
        )
        self.choice = Choice.objects.create(
            question=self.question,
            text='Test Choice'
        )

    def test_survey_creation(self):
        self.assertEqual(self.survey.title, 'Test Survey')
        self.assertEqual(self.survey.status, 'draft')
        self.assertEqual(self.survey.creator, self.user)

    def test_survey_is_active(self):
        # Publier le sondage d'abord
        self.survey.status = 'published'
        self.survey.save()
        self.assertTrue(self.survey.is_active())
        
        # Test avec un sondage expiré
        expired_survey = Survey.objects.create(
            title='Expired Survey',
            description='Expired',
            start_date=timezone.now() - timedelta(days=14),
            end_date=timezone.now() - timedelta(days=7),
            creator=self.user,
            status='published'
        )
        self.assertFalse(expired_survey.is_active())

    def test_survey_can_be_published(self):
        # Un sondage sans question ne peut pas être publié
        empty_survey = Survey.objects.create(
            title='Empty Survey',
            description='Empty',
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=7),
            creator=self.user
        )
        self.assertFalse(empty_survey.can_be_published())

        # Un sondage avec une question à choix et au moins 2 options peut être publié
        Choice.objects.create(
            question=self.question,
            text='Second Choice'
        )
        self.assertTrue(self.survey.can_be_published())

class SurveyViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = get_user_model().objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.other_user = get_user_model().objects.create_user(
            username='otheruser',
            password='testpass123'
        )
        self.survey = Survey.objects.create(
            title='Test Survey',
            description='Test Description',
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=7),
            creator=self.user,
            status='published'
        )

    def test_survey_list_view(self):
        # Test accès non authentifié
        response = self.client.get(reverse('surveys:survey_list'))
        self.assertEqual(response.status_code, 302)  # Redirection vers login

        # Test accès authentifié
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('surveys:survey_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'survey/survey_list.html')
        self.assertContains(response, 'Test Survey')

    def test_survey_create_view(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(reverse('surveys:survey_create'), {
            'title': 'New Survey',
            'description': 'New Description',
            'start_date': timezone.now(),
            'end_date': timezone.now() + timedelta(days=7)
        })
        self.assertEqual(response.status_code, 302)  # Redirection après création
        self.assertTrue(Survey.objects.filter(title='New Survey').exists())

    def test_survey_update_permissions(self):
        # Mettre le sondage en brouillon pour permettre la modification
        self.survey.status = 'draft'
        self.survey.save()

        # Test modification par le créateur
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(
            reverse('surveys:survey_update', kwargs={'pk': self.survey.pk})
        )
        self.assertEqual(response.status_code, 200)

        # Test modification par un autre utilisateur
        self.client.login(username='otheruser', password='testpass123')
        response = self.client.get(
            reverse('surveys:survey_update', kwargs={'pk': self.survey.pk})
        )
        self.assertEqual(response.status_code, 403)  # Forbidden

class SurveyParticipationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = get_user_model().objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.survey = Survey.objects.create(
            title='Test Survey',
            description='Test Description',
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=7),
            creator=self.user,
            status='published'
        )
        self.question = Question.objects.create(
            survey=self.survey,
            text='Test Question',
            question_type='single',
            required=True
        )
        self.choice = Choice.objects.create(
            question=self.question,
            text='Test Choice'
        )

    def test_survey_participation(self):
        self.client.login(username='testuser', password='testpass123')
        
        # Test soumission d'une réponse
        response = self.client.post(
            reverse('surveys:participate', kwargs={'pk': self.survey.pk}),
            {
                f'question_{self.question.id}': self.choice.id
            }
        )
        self.assertEqual(response.status_code, 302)  # Redirection après soumission
        
        # Vérifier que la réponse a été enregistrée
        self.assertTrue(Response.objects.filter(
            survey=self.survey,
            respondent=self.user
        ).exists())

    def test_duplicate_participation_prevention(self):
        self.client.login(username='testuser', password='testpass123')
        
        # Première participation
        self.client.post(
            reverse('surveys:participate', kwargs={'pk': self.survey.pk}),
            {
                f'question_{self.question.id}': self.choice.id
            }
        )
        
        # Tentative de deuxième participation
        response = self.client.get(
            reverse('surveys:participate', kwargs={'pk': self.survey.pk})
        )
        self.assertEqual(response.status_code, 403)  # Forbidden

class SurveySearchTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = get_user_model().objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.survey1 = Survey.objects.create(
            title='Python Survey',
            description='A survey about Python',
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=7),
            creator=self.user,
            status='published'
        )
        self.survey2 = Survey.objects.create(
            title='Django Survey',
            description='A survey about Django',
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=7),
            creator=self.user,
            status='draft'
        )

    def test_search_by_keyword(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('surveys:survey_list') + '?search=Python')
        self.assertContains(response, 'Python Survey')
        self.assertNotContains(response, 'Django Survey')

    def test_filter_by_status(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('surveys:survey_list') + '?status=published')
        self.assertContains(response, 'Python Survey')
        self.assertNotContains(response, 'Django Survey')

    def test_filter_by_creator(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('surveys:survey_list') + '?creator=testuser')
        self.assertContains(response, 'Python Survey')
        self.assertContains(response, 'Django Survey')

    def test_filter_by_date(self):
        self.client.login(username='testuser', password='testpass123')
        today = timezone.now().date()
        response = self.client.get(
            reverse('surveys:survey_list') + 
            f'?date_from={today}&date_to={today}'
        )
        self.assertContains(response, 'Python Survey')
        self.assertContains(response, 'Django Survey')
