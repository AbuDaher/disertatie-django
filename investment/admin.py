from django.contrib import admin
from .models import InvestmentAnalysis


@admin.register(InvestmentAnalysis)
class InvestmentAnalysisAdmin(admin.ModelAdmin):
    list_display = ('product', 'recommended_selling_price', 'profit_per_unit', 'profit_margin_percent', 'roi_percent', 'decision_label', 'created_at')
    list_filter = ('decision_label', 'created_at')
    search_fields = ('product__name', 'decision_reason')
    readonly_fields = ('commission_value', 'total_unit_cost', 'profit_per_unit', 'total_revenue', 'total_profit', 'profit_margin_percent', 'roi_percent', 'decision_label', 'decision_reason', 'created_at')
