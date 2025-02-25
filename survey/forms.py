from django import forms
from django.forms import inlineformset_factory
from .models import Survey, Question, Choice

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
            'order': forms.HiddenInput(),
        }


class ChoiceForm(forms.ModelForm):
    class Meta:
        model = Choice
        fields = ['text', 'order']
        widgets = {
            'order': forms.HiddenInput(),
        }


# FormSets pour gérer plusieurs questions et choix
QuestionFormSet = inlineformset_factory(
    Survey, 
    Question, 
    form=QuestionForm,
    extra=1, 
    can_delete=True
)

ChoiceFormSet = inlineformset_factory(
    Question, 
    Choice, 
    form=ChoiceForm, 
    extra=3, 
    can_delete=True
)


class SurveyPublishForm(forms.ModelForm):
    class Meta:
        model = Survey
        fields = ['status']
        widgets = {
            'status': forms.HiddenInput(),
        }