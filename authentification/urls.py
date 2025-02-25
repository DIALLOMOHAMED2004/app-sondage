from django.urls import path
from authentification import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.home, name='home'),
    path('signup', views.signup, name='signup'),
    path('signin', views.signin, name='signin'),
    path('signout', views.signout, name='signout'),
    path('activate/<uidb64>/<token>', views.activate, name='activate'),
    path('profile/', views.profile, name='profile'),
    path('profile/role/', views.RoleUpdateView.as_view(), name='role_update'),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('password_reset/', auth_views.PasswordResetView.as_view(template_name='authentification/password_reset.html'), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='authentification/password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='authentification/password_reset_confirm.html'), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='authentification/password_reset_complete.html'), name='password_reset_complete'),
]
