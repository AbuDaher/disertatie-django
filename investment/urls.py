from django.urls import path
from . import views

urlpatterns = [
    path('', views.analysis_history, name='investment_history'),
    path('produs/<int:product_id>/', views.create_analysis, name='investment_create'),
    path('rezultat/<int:pk>/', views.analysis_detail, name='investment_detail'),
]
