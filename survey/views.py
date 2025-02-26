from django import forms
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View
from django.views.generic.detail import SingleObjectMixin
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.http import HttpResponseRedirect, JsonResponse
from django.db import transaction
from django.contrib import messages
from django.forms import formset_factory
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Survey, Question, Choice, Response, Answer
from django.db.models import Q
from .forms import SurveyForm, QuestionForm, QuestionFormSet, ChoiceFormSet, SurveyPublishForm, AnswerForm, SurveySearchForm



class SurveyListView(LoginRequiredMixin, ListView):
    model = Survey
    template_name = 'survey/survey_list.html'
    context_object_name = 'surveys'
    paginate_by = 10

    def get_queryset(self):
        queryset = Survey.objects.all()
        form = SurveySearchForm(self.request.GET)

        if form.is_valid():
            # Recherche par mot-clé dans le titre ou la description
            search = form.cleaned_data.get('search')
            if search:
                queryset = queryset.filter(
                    Q(title__icontains=search) |
                    Q(description__icontains=search)
                )

            # Filtrage par créateur
            creator = form.cleaned_data.get('creator')
            if creator:
                queryset = queryset.filter(
                    creator__username__icontains=creator
                )

            # Filtrage par date
            date_from = form.cleaned_data.get('date_from')
            if date_from:
                queryset = queryset.filter(created_at__date__gte=date_from)

            date_to = form.cleaned_data.get('date_to')
            if date_to:
                queryset = queryset.filter(created_at__date__lte=date_to)

            # Filtrage par statut
            status = form.cleaned_data.get('status')
            if status:
                queryset = queryset.filter(status=status)

        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = SurveySearchForm(self.request.GET)
        
        # Ajouter des statistiques de base
        context['total_surveys'] = self.get_queryset().count()
        context['published_surveys'] = self.get_queryset().filter(status='published').count()
        context['draft_surveys'] = self.get_queryset().filter(status='draft').count()
        
        return context


class SurveyDetailView(LoginRequiredMixin, DetailView):
    model = Survey
    template_name = 'survey/survey_detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_creator'] = self.object.creator == self.request.user
        return context


class SurveyCreateView(LoginRequiredMixin, CreateView):
    model = Survey
    template_name = 'survey/survey_form.html'
    fields = ['title', 'description', 'start_date', 'end_date']

    def form_valid(self, form):
        form.instance.creator = self.request.user
        form.instance.status = 'draft'
        return super().form_valid(form)


class SurveyUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Survey
    template_name = 'survey/survey_form.html'
    fields = ['title', 'description', 'start_date', 'end_date']

    def test_func(self):
        survey = self.get_object()
        # Vérifier si l'utilisateur est le créateur
        if survey.creator != self.request.user:
            return False
        # Vérifier si le sondage peut être édité
        if survey.status == 'published':
            messages.error(self.request, "Un sondage publié ne peut pas être modifié.")
            return False
        if survey.end_date and survey.end_date < timezone.now():
            messages.error(self.request, "Un sondage terminé ne peut pas être modifié.")
            return False
        return True

    def form_valid(self, form):
        # Validation supplémentaire des dates
        if form.cleaned_data['start_date'] >= form.cleaned_data['end_date']:
            messages.error(self.request, "La date de début doit être antérieure à la date de fin.")
            return self.form_invalid(form)
        if form.cleaned_data['end_date'] < timezone.now():
            messages.error(self.request, "La date de fin ne peut pas être dans le passé.")
            return self.form_invalid(form)
        return super().form_valid(form)


class SurveyDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Survey
    template_name = 'survey/survey_confirm_delete.html'
    success_url = reverse_lazy('surveys:survey_list')

    def test_func(self):
        survey = self.get_object()
        # Seul le créateur peut supprimer le sondage
        if survey.creator != self.request.user:
            messages.error(self.request, "Vous n'êtes pas autorisé à supprimer ce sondage.")
            return False
        # Empêcher la suppression d'un sondage publié avec des réponses
        if survey.status == 'published' and survey.responses.exists():
            messages.error(self.request, "Impossible de supprimer un sondage publié qui a déjà des réponses.")
            return False
        return True


class SurveyEditQuestionsView(LoginRequiredMixin, UserPassesTestMixin, SingleObjectMixin, View):
    model = Survey
    template_name = 'survey/survey_edit_questions.html'
    
    def test_func(self):
        survey = self.get_object()
        return survey.creator == self.request.user and survey.can_be_edited()
    
    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        question_formset = QuestionFormSet(instance=self.object)
        return render(request, self.template_name, {
            'survey': self.object,
            'question_formset': question_formset,
        })

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        question_formset = QuestionFormSet(request.POST, instance=self.object)
        
        try:
            if question_formset.is_valid():
                with transaction.atomic():
                    # Sauvegarde du formset
                    questions = question_formset.save(commit=False)
                    
                    # Mise à jour de l'ordre pour chaque question
                    for i, question in enumerate(questions):
                        question.order = i + 1
                        question.save()
                    
                    # Suppression des questions marquées pour suppression
                    for obj in question_formset.deleted_objects:
                        obj.delete()
                    
                    messages.success(request, "Les questions ont été sauvegardées avec succès.")
                    return redirect('surveys:survey_detail', pk=self.object.pk)
            else:
                for form in question_formset:
                    for field, errors in form.errors.items():
                        for error in errors:
                            messages.error(request, f"Erreur dans le champ {field}: {error}")
                if question_formset.non_form_errors():
                    for error in question_formset.non_form_errors():
                        messages.error(request, error)
                
        except Exception as e:
            messages.error(request, f"Une erreur est survenue : {str(e)}")
        
        return render(request, self.template_name, {
            'survey': self.object,
            'question_formset': question_formset,
        })


class QuestionChoicesView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = 'survey/question_choices.html'
    
    def get_question(self):
        return get_object_or_404(Question, pk=self.kwargs['pk'])
    
    def test_func(self):
        question = self.get_question()
        # Vérifier que la question n'est pas de type texte
        if question.question_type == 'text':
            return False
        return question.survey.creator == self.request.user and question.survey.can_be_edited()
    
    def get(self, request, *args, **kwargs):
        question = self.get_question()
        choice_formset = ChoiceFormSet(instance=question)
        
        return render(request, self.template_name, {
            'question': question,
            'choice_formset': choice_formset,
        })
    
    def post(self, request, *args, **kwargs):
        question = self.get_question()
        choice_formset = ChoiceFormSet(request.POST, instance=question)
        
        try:
            if choice_formset.is_valid():
                with transaction.atomic():
                    # Sauvegarde du formset
                    choices = choice_formset.save(commit=False)
                    
                    # Mise à jour de l'ordre pour chaque choix
                    for i, choice in enumerate(choices):
                        choice.order = i + 1
                        choice.save()
                    
                    # Gestion des suppressions
                    for obj in choice_formset.deleted_objects:
                        obj.delete()
                    
                    messages.success(request, "Les choix ont été sauvegardés avec succès.")
                    return redirect('surveys:survey_edit_questions', pk=question.survey.pk)
            else:
                for form in choice_formset:
                    for field, errors in form.errors.items():
                        for error in errors:
                            messages.error(request, f"Erreur dans le choix : {error}")
                if choice_formset.non_form_errors():
                    for error in choice_formset.non_form_errors():
                        messages.error(request, error)
        except Exception as e:
            messages.error(request, f"Une erreur est survenue : {str(e)}")
        
        return render(request, self.template_name, {
            'question': question,
            'choice_formset': choice_formset,
        })


class SurveyPublishView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Survey
    template_name = 'survey/survey_publish.html'
    fields = []  # Pas de champs à éditer

    def test_func(self):
        survey = self.get_object()
        # Vérifier si l'utilisateur est le créateur
        if survey.creator != self.request.user:
            messages.error(self.request, "Vous n'êtes pas autorisé à publier ce sondage.")
            return False
        # Vérifier si le sondage peut être publié
        if survey.status == 'published':
            messages.error(self.request, "Ce sondage est déjà publié.")
            return False
        # Vérifier les dates
        if survey.end_date < timezone.now():
            messages.error(self.request, "La date de fin ne peut pas être dans le passé.")
            return False
        return True

    def form_valid(self, form):
        survey = form.instance
        # Vérifier qu'il y a au moins une question
        if not survey.questions.exists():
            messages.error(self.request, "Le sondage doit contenir au moins une question.")
            return self.form_invalid(form)
        
        # Vérifier que chaque question a des options si nécessaire
        for question in survey.questions.all():
            if question.question_type in ['single', 'multiple']:
                if not question.choices.exists():
                    messages.error(self.request, f"La question '{question.text}' doit avoir au moins une option.")
                    return self.form_invalid(form)
        
        survey.status = 'published'
        messages.success(self.request, "Le sondage a été publié avec succès!")
        return super().form_valid(form)

class AvailableSurveyListView(LoginRequiredMixin, ListView):
    model = Survey
    template_name = 'survey/available_surveys.html'
    context_object_name = 'surveys'

    def get_queryset(self):
        now = timezone.now()
        user = self.request.user
        # Retourne les sondages publiés, actifs, auxquels l'utilisateur n'a pas encore participé
        return Survey.objects.filter(
            status='published',
            start_date__lte=now,
            end_date__gte=now
        ).exclude(
            responses__respondent=user
        ).order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['now'] = timezone.now()
        return context


class SurveyParticipateView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Survey
    template_name = 'survey/participate.html'
    context_object_name = 'survey'

    def test_func(self):
        survey = self.get_object()
        now = timezone.now()
        
        # Vérifier si le sondage est publié
        if survey.status != 'published':
            messages.error(self.request, "Ce sondage n'est pas encore publié.")
            return False
            
        # Vérifier les dates
        if now < survey.start_date:
            messages.error(self.request, "Ce sondage n'a pas encore commencé.")
            return False
        if now > survey.end_date:
            messages.error(self.request, "Ce sondage est terminé.")
            return False
            
        # Vérifier si l'utilisateur n'a pas déjà répondu
        if Response.objects.filter(survey=survey, respondent=self.request.user).exists():
            messages.error(self.request, "Vous avez déjà participé à ce sondage.")
            return False
            
        return True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        survey = self.get_object()
        
        # Créer un formulaire pour chaque question
        question_forms = []
        for question in survey.questions.all().order_by('order'):
            form = AnswerForm(question=question, prefix=f'question_{question.id}')
            question_forms.append((question, form))
        
        context['question_forms'] = question_forms
        return context

    def post(self, request, *args, **kwargs):
        survey = self.get_object()
        
        # Vérifier à nouveau les conditions
        if not self.test_func():
            return redirect('surveys:survey_list')

        # Créer les formulaires avec les données POST
        question_forms = []
        has_errors = False
        
        for question in survey.questions.all().order_by('order'):
            form = AnswerForm(
                question=question,
                data=request.POST,
                prefix=f'question_{question.id}'
            )
            if question.required and not form.is_valid():
                has_errors = True
            question_forms.append((question, form))

        if has_errors:
            context = self.get_context_data(object=survey)
            context['question_forms'] = question_forms
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
            return render(request, self.template_name, context)

        try:
            with transaction.atomic():
                # Créer la réponse
                response = Response.objects.create(
                    survey=survey,
                    respondent=request.user
                )
                
                # Sauvegarder les réponses
                for question, form in question_forms:
                    if form.is_valid():
                        answer = form.save(commit=False)
                        answer.response = response
                        answer.question = question
                        answer.save()
                        
                        # Gérer les choix pour les questions à choix
                        if question.question_type in ['single', 'multiple']:
                            form.save_m2m()
                
                messages.success(request, "Merci pour votre participation!")
                return redirect('surveys:survey_results', pk=survey.pk)
                
        except Exception as e:
            messages.error(request, f"Une erreur est survenue lors de l'enregistrement de vos réponses : {str(e)}")
            context = self.get_context_data(object=survey)
            context['question_forms'] = question_forms
            return render(request, self.template_name, context)


class SurveyResultsView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Survey
    template_name = 'survey/results.html'
    context_object_name = 'survey'

    def test_func(self):
        survey = self.get_object()
        user = self.request.user
        now = timezone.now()
        
        # Le créateur peut toujours voir les résultats
        if survey.creator == user:
            return True
            
        # Pour les autres utilisateurs :
        # 1. Le sondage doit être terminé
        # 2. L'utilisateur doit avoir participé
        has_participated = Response.objects.filter(
            survey=survey,
            respondent=user
        ).exists()
        
        return now > survey.end_date and has_participated

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        survey = self.get_object()
        now = timezone.now()
        
        # Ajouter des informations sur l'accès aux résultats
        context['is_creator'] = survey.creator == self.request.user
        context['is_ended'] = now > survey.end_date
        context['has_participated'] = Response.objects.filter(
            survey=survey,
            respondent=self.request.user
        ).exists()
        
        # Calculer les statistiques pour chaque question
        questions_stats = []
        for question in survey.questions.all():
            stats = {
                'question': question,
                'total_responses': Answer.objects.filter(question=question).count(),
            }
            
            if question.question_type == 'text':
                # Pour les questions texte, récupérer toutes les réponses
                stats['text_answers'] = Answer.objects.filter(
                    question=question
                ).values_list('text_answer', flat=True)
            else:
                # Pour les questions à choix, calculer les pourcentages
                total = Answer.objects.filter(question=question).count()
                choices_stats = []
                
                for choice in question.choices.all():
                    choice_count = Answer.objects.filter(
                        question=question,
                        selected_choices=choice
                    ).count()
                    
                    percentage = (choice_count / total * 100) if total > 0 else 0
                    choices_stats.append({
                        'choice': choice,
                        'count': choice_count,
                        'percentage': round(percentage, 1)
                    })
                
                stats['choices_stats'] = choices_stats
            
            questions_stats.append(stats)
        
        context['questions_stats'] = questions_stats
        context['total_participants'] = Response.objects.filter(survey=survey).count()
        
        return context