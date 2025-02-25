from django.db import models
from django.conf import settings
from django.utils import timezone
from django.urls import reverse

class Survey(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Brouillon'),
        ('published', 'Publié'),
    )
    
    title = models.CharField(max_length=255, verbose_name="Titre")
    description = models.TextField(verbose_name="Description")
    start_date = models.DateTimeField(verbose_name="Date de début")
    end_date = models.DateTimeField(verbose_name="Date de fin")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_surveys')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft', verbose_name="Statut")

    class Meta:
        verbose_name = "Sondage"
        verbose_name_plural = "Sondages"
        ordering = ['-created_at']

    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        return reverse('surveys:survey_detail', args=[self.pk])
    
    def is_published(self):
        return self.status == 'published'
    
    def is_active(self):
        now = timezone.now()
        return self.is_published() and self.start_date <= now <= self.end_date
    
    def can_be_edited(self):
        return not self.is_published()


class Question(models.Model):
    QUESTION_TYPES = (
        ('single', 'Réponse unique (bouton radio)'),
        ('multiple', 'Réponses multiples (cases à cocher)'),
        ('text', 'Réponse texte ouverte'),
    )
    
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name='questions')
    text = models.CharField(max_length=255, verbose_name="Texte de la question")
    question_type = models.CharField(max_length=10, choices=QUESTION_TYPES, verbose_name="Type de question")
    required = models.BooleanField(default=False, verbose_name="Obligatoire")
    order = models.PositiveIntegerField(default=0, verbose_name="Ordre")
    
    class Meta:
        verbose_name = "Question"
        verbose_name_plural = "Questions"
        ordering = ['order']
    
    def __str__(self):
        return self.text


class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices')
    text = models.CharField(max_length=255, verbose_name="Texte du choix")
    order = models.PositiveIntegerField(default=0, verbose_name="Ordre")
    
    class Meta:
        verbose_name = "Choix"
        verbose_name_plural = "Choix"
        ordering = ['order']
    
    def __str__(self):
        return self.text


class Response(models.Model):
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name='responses')
    respondent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='survey_responses')
    submitted_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Réponse au sondage"
        verbose_name_plural = "Réponses aux sondages"
        unique_together = ('survey', 'respondent')
    
    def __str__(self):
        return f"Réponse de {self.respondent.username} au sondage '{self.survey.title}'"


class Answer(models.Model):
    response = models.ForeignKey(Response, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_choices = models.ManyToManyField(Choice, blank=True, related_name='answers')
    text_answer = models.TextField(blank=True, null=True)
    
    class Meta:
        verbose_name = "Réponse à une question"
        verbose_name_plural = "Réponses aux questions"
        unique_together = ('response', 'question')
    
    def __str__(self):
        return f"Réponse à la question '{self.question.text}'"