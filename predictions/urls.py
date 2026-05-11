from django.urls import path
from . import views

urlpatterns = [
    path('produs/<int:product_id>/', views.prediction_detail, name='prediction_detail'),
    path('istoric/', views.prediction_history, name='prediction_history'),
]
