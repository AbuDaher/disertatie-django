from decimal import Decimal
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from analytics.models import AnalysisRun
from products.models import Product
from predictions.models import PredictionRun
from .forms import InvestmentAnalysisForm
from .models import InvestmentAnalysis
from .services import calculate_investment


def _initial_values(product: Product, run: PredictionRun | None) -> dict:
    recommended_price = run.recommended_price if run else product.current_price
    if product.cost:
        acquisition_cost = product.cost
    else:
        acquisition_cost = (Decimal(product.current_price) * Decimal('0.65')).quantize(Decimal('0.01'))
    return {
        'acquisition_cost': acquisition_cost,
        'shipping_cost': Decimal('5.00'),
        'marketing_cost': Decimal('3.00'),
        'other_costs': Decimal('0.00'),
        'platform_commission_percent': 10,
        'recommended_selling_price': recommended_price,
        'estimated_units': max(product.sales_volume or 1, 1),
    }


def _ensure_analysis_run_for_manual_investment(product: Product, run: PredictionRun | None) -> AnalysisRun:
    if run and run.analysis_run:
        return run.analysis_run
    title = f"Analiză investițională - {product.name}"
    analysis_run = AnalysisRun.objects.create(
        title=title[:255],
        source_type=AnalysisRun.SOURCE_MANUAL,
        products_count=1,
        predictions_count=1 if run else 0,
        status=AnalysisRun.STATUS_COMPLETED,
        notes="Verificare creată automat pentru o analiză investițională individuală.",
    )
    if run and not run.analysis_run:
        run.analysis_run = analysis_run
        run.save(update_fields=['analysis_run'])
    return analysis_run


def create_analysis(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    run = product.prediction_runs.first()

    if request.method == 'POST':
        form = InvestmentAnalysisForm(request.POST)
        if form.is_valid():
            analysis = form.save(commit=False)
            analysis.product = product
            analysis.prediction_run = run
            analysis.analysis_run = _ensure_analysis_run_for_manual_investment(product, run)
            analysis = calculate_investment(analysis)
            analysis.save()
            analysis.analysis_run.refresh_counters()
            return redirect(reverse('investment_detail', kwargs={'pk': analysis.pk}))
    else:
        form = InvestmentAnalysisForm(initial=_initial_values(product, run))

    return render(request, 'investment/analysis_form.html', {
        'form': form,
        'product': product,
        'run': run,
        'analysis_run': run.analysis_run if run else None,
    })


def analysis_detail(request, pk):
    analysis = get_object_or_404(
        InvestmentAnalysis.objects.select_related('product', 'prediction_run', 'analysis_run'),
        pk=pk,
    )
    return render(request, 'investment/analysis_detail.html', {
        'analysis': analysis,
        'product': analysis.product,
        'run': analysis.prediction_run,
        'analysis_run': analysis.analysis_run,
    })


def analysis_history(request):
    analyses = InvestmentAnalysis.objects.select_related('product', 'prediction_run', 'analysis_run').all()
    return render(request, 'investment/analysis_history.html', {'analyses': analyses})
