from django import forms
from django.forms import inlineformset_factory
from .models import Survey, Question, Choice, Response, Answer

class SurveyForm(forms.ModelForm):
    class Meta:
        model = Survey
        fields = ['title', 'description', 'start_date', 'end_date']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Titre du sondage'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Description du sondage'
            }),
            'start_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'end_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
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
            'text': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Texte de la question'
            }),
            'question_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'required': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
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
    min_num=1,
    validate_min=True,
    fields=['text', 'question_type', 'required', 'order'],
)

ChoiceFormSet = inlineformset_factory(
    Question,
    Choice,
    form=ChoiceForm,
    extra=1,
    can_delete=True,
    min_num=2,
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
        status = cleaned_data.get('status')
        
        if status == 'published':
            survey = self.instance
            if not survey.can_be_published():
                raise forms.ValidationError(
                    "Le sondage ne peut pas être publié. Assurez-vous qu'il contient au moins une question "
                    "et que chaque question de type choix unique ou multiple a au moins deux options."
                )
        
        return cleaned_data


class SurveyResponseForm(forms.ModelForm):
    class Meta:
        model = Response
        fields = []


class AnswerForm(forms.ModelForm):
    text_answer = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Votre réponse...'
        })
    )
    
    selected_choices = forms.ModelMultipleChoiceField(
        queryset=Choice.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input'
        })
    )
    
    single_choice = forms.ModelChoiceField(
        queryset=Choice.objects.none(),
        required=False,
        widget=forms.RadioSelect(attrs={
            'class': 'form-check-input'
        }),
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
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if commit:
            instance.save()
            if 'selected_choices' in self.cleaned_data:
                instance.selected_choices.set(self.cleaned_data['selected_choices'])
            elif 'single_choice' in self.cleaned_data and self.cleaned_data['single_choice']:
                instance.selected_choices.set([self.cleaned_data['single_choice']])
        return instance


class SurveySearchForm(forms.Form):
    search = forms.CharField(
        required=False,
        label='Rechercher',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Rechercher par titre ou description...',
        })
    )
    
    creator = forms.CharField(
        required=False,
        label='Créateur',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nom du créateur...',
        })
    )
    
    date_from = forms.DateField(
        required=False,
        label='Date de début',
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
        })
    )
    
    date_to = forms.DateField(
        required=False,
        label='Date de fin',
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
        })
    )
    
    status = forms.ChoiceField(
        required=False,
        label='Statut',
        choices=(('', 'Tous'),) + Survey.STATUS_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )