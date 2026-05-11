from django.contrib import admin
from .models import AnalysisRun


@admin.register(AnalysisRun)
class AnalysisRunAdmin(admin.ModelAdmin):
    list_display = ("title", "source_type", "products_count", "predictions_count", "investment_count", "status", "created_at")
    list_filter = ("source_type", "status", "created_at")
    search_fields = ("title", "keyword", "source_file_name", "notes")
    readonly_fields = ("created_at", "updated_at")
