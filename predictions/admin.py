from django.contrib import admin
from .models import PredictionRun

@admin.register(PredictionRun)
class PredictionRunAdmin(admin.ModelAdmin):
    list_display = ('product', 'success_label', 'success_probability', 'recommended_price', 'created_at')
    list_filter = ('success_label',)
