from django import forms
from django.forms import inlineformset_factory
from .models import Survey, Question, Choice, Response, Answer

class SurveyForm(forms.ModelForm):
    class Meta:
        model = Survey
        fields = ['title', 'description', 'start_date', 'end_date']
        widgets = {
            'start_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'end_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date and start_date >= end_date:
            raise forms.ValidationError("La date de fin doit être postérieure à la date de début.")
        
        return cleaned_data


class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ['text', 'question_type', 'required', 'order']
        widgets = {
            'text': forms.TextInput(attrs={'class': 'form-control'}),
            'question_type': forms.Select(attrs={'class': 'form-select'}),
            'required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'order': forms.HiddenInput(),
        }

    def clean_text(self):
        text = self.cleaned_data.get('text')
        if not text:
            raise forms.ValidationError("Ce champ est obligatoire.")
        return text

    def clean_question_type(self):
        question_type = self.cleaned_data.get('question_type')
        if not question_type:
            raise forms.ValidationError("Ce champ est obligatoire.")
        return question_type


class ChoiceForm(forms.ModelForm):
    class Meta:
        model = Choice
        fields = ['text', 'order']
        widgets = {
            'text': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Texte du choix'
            }),
            'order': forms.HiddenInput(),
        }

    def clean_text(self):
        text = self.cleaned_data.get('text')
        if not text:
            raise forms.ValidationError("Le texte du choix est obligatoire.")
        return text


# FormSets pour gérer plusieurs questions et choix
QuestionFormSet = inlineformset_factory(
    Survey, 
    Question, 
    form=QuestionForm,
    extra=1, 
    can_delete=True,
    min_num=1,  # Au moins une question requise
    validate_min=True,  # Valider le nombre minimum
    fields=['text', 'question_type', 'required', 'order'],
)

ChoiceFormSet = inlineformset_factory(
    Question,
    Choice,
    form=ChoiceForm,
    extra=1,
    can_delete=True,
    min_num=2,  # Au moins deux choix requis
    validate_min=True,
    fields=['text', 'order'],
)


class SurveyPublishForm(forms.ModelForm):
    class Meta:
        model = Survey
        fields = ['status']
        widgets = {
            'status': forms.HiddenInput()
        }

    def clean(self):
        cleaned_data = super().clean()
        survey = self.instance
        
        # Vérifier le nombre de questions
        if survey.questions.count() < 1:
            raise forms.ValidationError("Le sondage doit contenir au moins une question.")
        
        # Vérifier les choix pour les questions non textuelles
        for question in survey.questions.all():
            if question.question_type in ['single', 'multiple']:
                if question.choices.count() < 2:
                    raise forms.ValidationError(
                        f"La question '{question.text}' doit avoir au moins 2 choix."
                    )
        
        return cleaned_data


class SurveyResponseForm(forms.ModelForm):
    class Meta:
        model = Response
        fields = []  # Pas de champs directs, car les réponses sont gérées par les Answer

class AnswerForm(forms.ModelForm):
    text_answer = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
    )
    selected_choices = forms.ModelMultipleChoiceField(
        queryset=Choice.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple
    )
    single_choice = forms.ModelChoiceField(
        queryset=Choice.objects.none(),
        required=False,
        widget=forms.RadioSelect,
        empty_label=None
    )

    class Meta:
        model = Answer
        fields = ['text_answer', 'selected_choices', 'single_choice']

    def __init__(self, question, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if question.question_type in ['single', 'multiple']:
            choices = question.choices.all()
            if question.question_type == 'single':
                self.fields['single_choice'].queryset = choices
                self.fields['single_choice'].required = question.required
                del self.fields['selected_choices']
            else:  # multiple
                self.fields['selected_choices'].queryset = choices
                self.fields['selected_choices'].required = question.required
                del self.fields['single_choice']
            del self.fields['text_answer']
        else:  # text
            self.fields['text_answer'].required = question.required
            del self.fields['selected_choices']
            del self.fields['single_choice']

    def clean(self):
        cleaned_data = super().clean()
        if 'single_choice' in cleaned_data and cleaned_data.get('single_choice'):
            # Convertir le choix unique en liste pour la sauvegarde
            cleaned_data['selected_choices'] = [cleaned_data.pop('single_choice')]
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if hasattr(self, 'cleaned_data') and 'selected_choices' in self.cleaned_data:
            instance.selected_choices.set(self.cleaned_data['selected_choices'])
        if commit:
            instance.save()
        return instance