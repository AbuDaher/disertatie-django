from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('produse/adauga/', views.product_create, name='product_create'),
    path('produse/<int:pk>/', views.product_detail, name='product_detail'),
]
