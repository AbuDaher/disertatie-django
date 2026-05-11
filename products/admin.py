from django.contrib import admin
from .models import Product

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'current_price', 'rating', 'sales_volume', 'created_at')
    search_fields = ('name', 'category', 'brand')
