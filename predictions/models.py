from django.db import models
from products.models import Product


class PredictionRun(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='prediction_runs')
    analysis_run = models.ForeignKey(
        'analytics.AnalysisRun',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='prediction_runs',
        help_text='Verificarea / sesiunea de analiză din care face parte predicția.',
    )
    success_probability = models.FloatField()
    success_label = models.CharField(max_length=80)
    recommended_price = models.DecimalField(max_digits=10, decimal_places=2)
    model_name_classifier = models.CharField(max_length=120, default='baseline_classifier')
    model_name_regressor = models.CharField(max_length=120, default='baseline_regressor')
    explanation = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.product.name} - {self.success_label}'
