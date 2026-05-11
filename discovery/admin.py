from django.contrib import admin
from .models import DiscoveredProduct, SearchQuery


@admin.register(SearchQuery)
class SearchQueryAdmin(admin.ModelAdmin):
    list_display = ('keyword', 'category', 'top_n', 'data_source', 'used_source', 'created_at')
    search_fields = ('keyword', 'category')
    list_filter = ('data_source', 'used_source')


@admin.register(DiscoveredProduct)
class DiscoveredProductAdmin(admin.ModelAdmin):
    list_display = ('title', 'source', 'price', 'currency', 'commercial_score', 'rating', 'review_count', 'estimated_orders')
    search_fields = ('title', 'brand', 'seller_username')
    list_filter = ('source', 'currency', 'condition')
