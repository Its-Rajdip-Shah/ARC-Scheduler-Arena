"""Authentication routes, mounted at /api/auth/."""

from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

app_name = 'accounts'

urlpatterns = [
    path('register/', views.RegisterView.as_view(), name='register'),
    path('mfa/enroll/confirm/', views.MFAEnrolConfirmView.as_view(), name='mfa-enrol-confirm'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('login/mfa/', views.MFAVerifyView.as_view(), name='login-mfa'),
    path('admin/login/', views.AdminLoginView.as_view(), name='admin-login'),
    path('admin/login/mfa/', views.AdminMFAVerifyView.as_view(), name='admin-login-mfa'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('me/', views.MeView.as_view(), name='me'),
]
