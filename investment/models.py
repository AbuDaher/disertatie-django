from django.db import models
from products.models import Product
from predictions.models import PredictionRun


class InvestmentAnalysis(models.Model):
    DECISION_RECOMMENDED = 'recommended'
    DECISION_MEDIUM_RISK = 'medium_risk'
    DECISION_NOT_RECOMMENDED = 'not_recommended'

    DECISION_CHOICES = [
        (DECISION_RECOMMENDED, 'Merită investiția'),
        (DECISION_MEDIUM_RISK, 'Merită cu risc mediu'),
        (DECISION_NOT_RECOMMENDED, 'Nu este recomandată investiția'),
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='investment_analyses')
    prediction_run = models.ForeignKey(PredictionRun, on_delete=models.SET_NULL, null=True, blank=True, related_name='investment_analyses')
    analysis_run = models.ForeignKey(
        'analytics.AnalysisRun',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='investment_analyses',
        help_text='Verificarea / sesiunea de analiză din care face parte analiza investițională.',
    )

    acquisition_cost = models.DecimalField(max_digits=10, decimal_places=2, help_text='Cost achiziție / furnizor per produs')
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text='Transport / logistică per produs')
    marketing_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text='Cost promovare per produs')
    other_costs = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text='Alte costuri per produs')
    platform_commission_percent = models.FloatField(default=0, help_text='Comision platformă / marketplace (%)')
    recommended_selling_price = models.DecimalField(max_digits=10, decimal_places=2, help_text='Preț de vânzare propus')
    estimated_units = models.PositiveIntegerField(default=1, help_text='Număr estimat de unități vândute')

    commission_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    profit_per_unit = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_profit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    profit_margin_percent = models.FloatField(default=0)
    roi_percent = models.FloatField(default=0)

    decision_label = models.CharField(max_length=40, choices=DECISION_CHOICES, default=DECISION_MEDIUM_RISK)
    decision_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.product.name} - {self.get_decision_label_display()}'
