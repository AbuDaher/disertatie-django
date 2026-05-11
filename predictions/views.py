from django.shortcuts import get_object_or_404, render

from analytics.models import AnalysisRun
from products.models import Product
from .models import PredictionRun


XAI_KEYS = {
    'xai_tip_explicatie',
    'xai_rezumat',
    'xai_factori_pozitivi',
    'xai_factori_negativi',
    'xai_contributii_locale',
}


def _sort_explanation_items(explanation: dict):
    scalar_items = []
    for key, value in (explanation or {}).items():
        if key in XAI_KEYS:
            continue
        if isinstance(value, (dict, list, tuple)):
            continue
        scalar_items.append((key, value))

    def score(item):
        value = item[1]
        if isinstance(value, (int, float)):
            return abs(value)
        return 0

    return sorted(scalar_items, key=score, reverse=True)


def prediction_detail(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    run = product.prediction_runs.first()
    explanation_items = []
    xai = {}
    if run:
        explanation = run.explanation or {}
        explanation_items = _sort_explanation_items(explanation)
        xai = {
            'summary': explanation.get('xai_rezumat', ''),
            'type': explanation.get('xai_tip_explicatie', ''),
            'positive': explanation.get('xai_factori_pozitivi', []),
            'negative': explanation.get('xai_factori_negativi', []),
            'local': explanation.get('xai_contributii_locale', []),
        }
    return render(request, 'predictions/prediction_detail.html', {
        'product': product,
        'run': run,
        'analysis_run': run.analysis_run if run else None,
        'explanation_items': explanation_items,
        'xai': xai,
    })


def prediction_history(request):
    """Istoricul este restructurat pe verificări, nu pe predicții individuale amestecate."""
    analysis_runs = AnalysisRun.objects.all()
    legacy_runs = PredictionRun.objects.select_related('product').filter(analysis_run__isnull=True)[:25]
    return render(request, 'predictions/prediction_history.html', {
        'analysis_runs': analysis_runs,
        'legacy_runs': legacy_runs,
    })
