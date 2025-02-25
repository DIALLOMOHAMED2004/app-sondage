from django.urls import path
from . import views

app_name = 'surveys'

urlpatterns = [
    # Gestion des sondages
    path('', views.SurveyListView.as_view(), name='survey_list'),
    path('create/', views.SurveyCreateView.as_view(), name='survey_create'),
    path('<int:pk>/', views.SurveyDetailView.as_view(), name='survey_detail'),
    path('<int:pk>/update/', views.SurveyUpdateView.as_view(), name='survey_update'),
    path('<int:pk>/delete/', views.SurveyDeleteView.as_view(), name='survey_delete'),
    path('<int:pk>/edit-questions/', views.SurveyEditQuestionsView.as_view(), name='survey_edit_questions'),
    path('<int:pk>/publish/', views.SurveyPublishView.as_view(), name='survey_publish'),
    
    # Gestion des choix pour les questions
    path('question/<int:pk>/choices/', views.QuestionChoicesView.as_view(), name='question_choices'),
]