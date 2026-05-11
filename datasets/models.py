from django.db import models


class DatasetUpload(models.Model):
    file = models.FileField(upload_to='datasets/')
    original_name = models.CharField(max_length=255)
    rows_count = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=40, default='uploaded')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.original_name
