from django.urls import path
from . import views

urlpatterns = [
    path('upload/', views.dataset_upload, name='dataset_upload'),
]
