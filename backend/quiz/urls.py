"""URL routes for the quiz API."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register('questions', views.QuestionViewSet, basename='question')
router.register('attempts', views.AttemptViewSet, basename='attempt')

urlpatterns = [
    path('auth/csrf/', views.CsrfView.as_view(), name='csrf'),
    path('auth/login/', views.LoginView.as_view(), name='login'),
    path('auth/logout/', views.LogoutView.as_view(), name='logout'),
    path('auth/me/', views.me_view, name='me'),
    path('', include(router.urls)),
]
