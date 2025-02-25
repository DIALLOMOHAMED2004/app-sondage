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
from .forms import SurveyForm, QuestionForm, QuestionFormSet, ChoiceFormSet, SurveyPublishForm, AnswerForm



class SurveyListView(LoginRequiredMixin, ListView):
    model = Survey
    template_name = 'survey/survey_list.html'
    context_object_name = 'surveys'

    def get_queryset(self):
        # Obtenir tous les sondages publiés
        return Survey.objects.filter(status='published').order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        now = timezone.now()

        # Pour chaque sondage, déterminer les actions possibles
        surveys_with_actions = []
        for survey in context['surveys']:
            actions = {
                'can_participate': False,
                'can_view_results': False,
                'is_creator': survey.creator == user,
                'has_participated': survey.responses.filter(respondent=user).exists(),
                'is_active': survey.start_date <= now <= survey.end_date,
                'is_finished': now > survey.end_date
            }

            # Peut participer si :
            # - N'est pas le créateur OU le créateur est autorisé à participer
            # - N'a pas déjà participé
            # - Le sondage est actif (entre dates de début et fin)
            if not actions['has_participated'] and actions['is_active']:
                actions['can_participate'] = True

            # Peut voir les résultats si :
            # - Est le créateur OU le sondage est terminé
            actions['can_view_results'] = actions['is_creator'] or actions['is_finished']

            surveys_with_actions.append({
                'survey': survey,
                'actions': actions
            })

        context['surveys_with_actions'] = surveys_with_actions
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
    form_class = SurveyForm
    template_name = 'survey/survey_form.html'
    
    def form_valid(self, form):
        # Définir l'utilisateur actuel comme créateur du sondage
        form.instance.creator = self.request.user
        form.instance.status = 'draft'
        
        # Sauvegarder l'objet Survey
        self.object = form.save()
        
        # Rediriger vers la page d'édition des questions
        return HttpResponseRedirect(reverse('surveys:survey_edit_questions', args=[self.object.pk]))


class SurveyUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Survey
    form_class = SurveyForm
    template_name = 'survey/survey_form.html'
    
    def test_func(self):
        # Vérifier que l'utilisateur est le créateur du sondage
        survey = self.get_object()
        return survey.creator == self.request.user and survey.can_be_edited()
    
    def form_valid(self, form):
        # Sauvegarder le sondage
        self.object = form.save()
        
        # Rediriger vers la page d'édition des questions
        return HttpResponseRedirect(reverse('surveys:survey_edit_questions', args=[self.object.pk]))


class SurveyDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Survey
    template_name = 'survey/survey_confirm_delete.html'
    success_url = reverse_lazy('surveys:survey_list')
    
    def test_func(self):
        # Vérifier que l'utilisateur est le créateur du sondage et qu'il n'est pas publié
        survey = self.get_object()
        return survey.creator == self.request.user and survey.can_be_edited()


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
    form_class = SurveyPublishForm
    template_name = 'survey/survey_publish.html'
    
    def test_func(self):
        survey = self.get_object()
        return survey.creator == self.request.user and survey.can_be_edited()
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if self.request.method == 'GET':
            kwargs['initial'] = {'status': 'published'}
        return kwargs
    
    def form_valid(self, form):
        try:
            # La validation est maintenant gérée dans le formulaire
            form.instance.status = 'published'
            response = super().form_valid(form)
            messages.success(self.request, "Le sondage a été publié avec succès.")
            return response
        except forms.ValidationError as e:
            messages.error(self.request, str(e))
            return self.form_invalid(form)
    
    def form_invalid(self, form):
        for error in form.non_field_errors():
            messages.error(self.request, error)
        return super().form_invalid(form)
    
    def get_success_url(self):
        return reverse('surveys:survey_detail', kwargs={'pk': self.object.pk})


class AvailableSurveyListView(LoginRequiredMixin, ListView):
    model = Survey
    template_name = 'survey/available_surveys.html'
    context_object_name = 'surveys'

    def get_queryset(self):
        now = timezone.now()
        # Obtenir les sondages publiés et actifs
        available_surveys = Survey.objects.filter(
            status='published',
            start_date__lte=now,
            end_date__gte=now
        )
        # Exclure les sondages auxquels l'utilisateur a déjà répondu
        return available_surveys.exclude(
            responses__respondent=self.request.user
        )


class SurveyParticipateView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Survey
    template_name = 'survey/participate.html'
    context_object_name = 'survey'

    def test_func(self):
        survey = self.get_object()
        # Vérifier si le sondage est publié et actif
        if not survey.is_active():
            messages.error(self.request, "Ce sondage n'est pas actif.")
            return False
        # Vérifier si l'utilisateur n'a pas déjà répondu
        if Response.objects.filter(survey=survey, respondent=self.request.user).exists():
            messages.error(self.request, "Vous avez déjà participé à ce sondage.")
            return False
        return True

    def handle_no_permission(self):
        return redirect('surveys:survey_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        survey = self.get_object()
        
        # Créer un formulaire pour chaque question
        question_forms = []
        for question in survey.questions.all():
            form = AnswerForm(question=question, prefix=f'question_{question.id}')
            question_forms.append((question, form))
        
        context['question_forms'] = question_forms
        return context

    def post(self, request, *args, **kwargs):
        survey = self.get_object()
        
        # Vérifier à nouveau si l'utilisateur n'a pas déjà répondu
        if Response.objects.filter(survey=survey, respondent=request.user).exists():
            messages.error(request, "Vous avez déjà participé à ce sondage.")
            return redirect('surveys:survey_list')

        question_forms = []
        forms_valid = True

        try:
            with transaction.atomic():
                # Créer la réponse principale
                response = Response.objects.create(
                    survey=survey,
                    respondent=request.user
                )

                # Traiter chaque question
                for question in survey.questions.all():
                    form = AnswerForm(
                        question=question,
                        data=request.POST,
                        prefix=f'question_{question.id}'
                    )
                    
                    if form.is_valid():
                        answer = Answer.objects.create(
                            response=response,
                            question=question,
                            text_answer=form.cleaned_data.get('text_answer', '')
                        )
                        
                        # Gérer les choix sélectionnés
                        if question.question_type in ['single', 'multiple']:
                            selected_choices = []
                            if question.question_type == 'single':
                                single_choice = form.cleaned_data.get('single_choice')
                                if single_choice:
                                    selected_choices = [single_choice]
                            else:
                                selected_choices = form.cleaned_data.get('selected_choices', [])
                            
                            if selected_choices:
                                answer.selected_choices.set(selected_choices)
                    else:
                        forms_valid = False
                        question_forms.append((question, form))

                if not forms_valid:
                    raise ValidationError("Certaines réponses sont invalides.")

                messages.success(request, "Merci d'avoir participé à ce sondage !")
                return redirect('surveys:survey_list')

        except ValidationError:
            # En cas d'erreur de validation, annuler la transaction
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
            return render(request, self.template_name, {
                'survey': survey,
                'question_forms': question_forms
            })
        except Exception as e:
            # En cas d'erreur inattendue, annuler la transaction
            messages.error(request, "Une erreur est survenue lors de l'enregistrement de vos réponses.")
            return redirect('surveys:survey_list')


class SurveyResultsView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Survey
    template_name = 'survey/results.html'
    context_object_name = 'survey'

    def test_func(self):
        survey = self.get_object()
        user = self.request.user
        
        # Le créateur peut toujours voir les résultats
        if survey.creator == user:
            return True
            
        # Les participants ne peuvent voir les résultats qu'après la date de fin
        if timezone.now() > survey.end_date:
            return True
            
        return False

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        survey = self.get_object()
        
        # Préparer les statistiques pour chaque question
        questions_stats = []
        for question in survey.questions.all():
            stats = {
                'question': question,
                'total_responses': question.answers.count(),
                'choices_stats': []
            }
            
            if question.question_type in ['single', 'multiple']:
                # Calculer les statistiques pour chaque choix
                for choice in question.choices.all():
                    choice_count = choice.answers.count()
                    percentage = (choice_count / stats['total_responses'] * 100) if stats['total_responses'] > 0 else 0
                    stats['choices_stats'].append({
                        'choice': choice,
                        'count': choice_count,
                        'percentage': round(percentage, 1)
                    })
            else:
                # Pour les questions texte, récupérer toutes les réponses
                stats['text_answers'] = question.answers.exclude(text_answer='')

            questions_stats.append(stats)
        
        context['questions_stats'] = questions_stats
        return context