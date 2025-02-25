from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View
from django.views.generic.detail import SingleObjectMixin
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.http import HttpResponseRedirect, JsonResponse
from django.db import transaction
from django.contrib import messages
from django.forms import formset_factory

from .models import Survey, Question, Choice, Response, Answer
from .forms import SurveyForm, QuestionForm, QuestionFormSet, ChoiceFormSet, SurveyPublishForm


class SurveyListView(LoginRequiredMixin, ListView):
    model = Survey
    template_name = 'survey/survey_list.html'
    context_object_name = 'surveys'
    
    def get_queryset(self):
        # Si l'utilisateur est créateur, montrer tous ses sondages
        return Survey.objects.filter(creator=self.request.user)


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
        # Vérifier que l'utilisateur est le créateur du sondage et qu'il n'est pas publié
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
        
        if question_formset.is_valid():
            question_formset.save()
            messages.success(request, "Les questions ont été sauvegardées avec succès.")
            return redirect('surveys:survey_detail', pk=self.object.pk)
        
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
        
        if choice_formset.is_valid():
            choice_formset.save()
            messages.success(request, "Les choix ont été sauvegardés avec succès.")
            return redirect('surveys:survey_edit_questions', pk=question.survey.pk)
        
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
            # Pré-remplir le formulaire
            kwargs['initial'] = {'status': 'published'}
        return kwargs
    
    def form_valid(self, form):
        # Vérifier que le sondage a au moins une question
        survey = self.get_object()
        if survey.questions.count() == 0:
            messages.error(self.request, "Le sondage doit contenir au moins une question avant d'être publié.")
            return redirect('surveys:survey_edit_questions', pk=survey.pk)
        
        # Vérifier que chaque question de type single ou multiple a au moins 2 choix
        for question in survey.questions.all():
            if question.question_type in ['single', 'multiple'] and question.choices.count() < 2:
                messages.error(self.request, f"La question '{question.text}' doit avoir au moins 2 choix.")
                return redirect('surveys:question_choices', pk=question.pk)
        
        # Publier le sondage
        form.instance.status = 'published'
        messages.success(self.request, "Le sondage a été publié avec succès.")
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('surveys:survey_detail', kwargs={'pk': self.object.pk})