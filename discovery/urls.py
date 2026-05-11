from django.urls import path
from . import views

urlpatterns = [
    path('', views.opportunity_search, name='opportunity_search'),
    path('cautare/<int:pk>/', views.search_results, name='discovery_search_results'),
    path('analizeaza/<int:pk>/', views.analyze_opportunity, name='analyze_opportunity'),
]
