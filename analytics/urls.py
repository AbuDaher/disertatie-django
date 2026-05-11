from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='analytics_dashboard'),
    path('verificare/<int:pk>/', views.analysis_run_detail, name='analysis_run_detail'),
    path('modele/', views.model_performance, name='model_performance'),
]
