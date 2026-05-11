from django.contrib import admin
from .models import DatasetUpload

@admin.register(DatasetUpload)
class DatasetUploadAdmin(admin.ModelAdmin):
    list_display = ('original_name', 'rows_count', 'status', 'created_at')
