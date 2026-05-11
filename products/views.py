from django.shortcuts import get_object_or_404, redirect, render

from analytics.models import AnalysisRun
from .forms import ProductForm
from .models import Product
from predictions.models import PredictionRun
from predictions.services import get_model_metadata, ml_artifacts_exist, predict_product


def home(request):
    products = Product.objects.all()[:10]
    runs = PredictionRun.objects.select_related('product')[:10]
    return render(request, 'products/home.html', {'products': products, 'runs': runs})


def product_create(request):
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save()
            analysis_run = AnalysisRun.objects.create(
                title=f"Evaluare manuală - {product.name}"[:255],
                source_type=AnalysisRun.SOURCE_MANUAL,
                products_count=1,
                status=AnalysisRun.STATUS_COMPLETED,
                notes="Verificare creată automat din formularul de evaluare produs.",
            )
            probability, label, price, explanation = predict_product(product)
            metadata = get_model_metadata()
            PredictionRun.objects.create(
                product=product,
                analysis_run=analysis_run,
                success_probability=probability,
                success_label=label,
                recommended_price=price,
                model_name_classifier=metadata.get('selected_classifier', 'ML classifier') if ml_artifacts_exist() else 'baseline_classifier',
                model_name_regressor=metadata.get('selected_regressor', 'ML regressor') if ml_artifacts_exist() else 'baseline_regressor',
                explanation=explanation,
            )
            analysis_run.refresh_counters()
            return redirect('prediction_detail', product_id=product.id)
    else:
        form = ProductForm()
    return render(request, 'products/product_form.html', {'form': form})


def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    return render(request, 'products/product_detail.html', {'product': product})
