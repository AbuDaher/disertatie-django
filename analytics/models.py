from django.db import models
from django.utils import timezone


class AnalysisRun(models.Model):
    """Reprezintă o verificare distinctă realizată în platformă.

    O verificare poate proveni din upload CSV, evaluare manuală, căutare de oportunități
    sau integrare API. Predicțiile și analizele investiționale sunt legate de această
    verificare, astfel încât dashboard-ul să nu amestece rezultate din rulări diferite.
    """

    SOURCE_MANUAL = "manual"
    SOURCE_CSV_UPLOAD = "csv_upload"
    SOURCE_DISCOVERY = "discovery"
    SOURCE_EBAY_API = "ebay_api"
    SOURCE_CSV_FALLBACK = "csv_fallback"

    SOURCE_CHOICES = [
        (SOURCE_MANUAL, "Evaluare manuală"),
        (SOURCE_CSV_UPLOAD, "Încărcare CSV"),
        (SOURCE_DISCOVERY, "Căutare oportunități"),
        (SOURCE_EBAY_API, "eBay API"),
        (SOURCE_CSV_FALLBACK, "CSV fallback"),
    ]

    STATUS_CREATED = "created"
    STATUS_COMPLETED = "completed"
    STATUS_ERROR = "error"

    STATUS_CHOICES = [
        (STATUS_CREATED, "Creată"),
        (STATUS_COMPLETED, "Finalizată"),
        (STATUS_ERROR, "Eroare"),
    ]

    title = models.CharField(max_length=255)
    source_type = models.CharField(max_length=40, choices=SOURCE_CHOICES, default=SOURCE_MANUAL)
    keyword = models.CharField(max_length=200, blank=True)
    source_file_name = models.CharField(max_length=255, blank=True)
    products_count = models.PositiveIntegerField(default=0)
    predictions_count = models.PositiveIntegerField(default=0)
    investment_count = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_CREATED)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Verificare analiză"
        verbose_name_plural = "Verificări analiză"

    def __str__(self):
        return self.title

    def refresh_counters(self):
        self.products_count = self.prediction_runs.values("product_id").distinct().count()
        self.predictions_count = self.prediction_runs.count()
        if hasattr(self, "investment_analyses"):
            self.investment_count = self.investment_analyses.count()
        self.save(update_fields=["products_count", "predictions_count", "investment_count", "updated_at"])
