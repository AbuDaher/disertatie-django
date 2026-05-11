from decimal import Decimal

from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from products.models import Product
from predictions.models import PredictionRun
from predictions.services import predict_product, ml_artifacts_exist

from .forms import OpportunitySearchForm
from .models import DiscoveredProduct, SearchQuery
from .services import discover_products


def opportunity_search(request):
    form = OpportunitySearchForm(request.POST or None)
    search_query = None
    discovered_products = []

    if request.method == 'POST' and form.is_valid():
        search_query = form.save(commit=False)
        search_query.top_n = int(form.cleaned_data['top_n'])
        search_query.save()

        result = discover_products(search_query)
        search_query.used_source = result.used_source
        search_query.status_message = result.status_message
        search_query.save(update_fields=['used_source', 'status_message'])

        for item in result.products:
            discovered_products.append(DiscoveredProduct.objects.create(
                search_query=search_query,
                source=item.get('source', 'csv_fallback'),
                external_id=item.get('external_id', ''),
                title=item.get('title', ''),
                category=item.get('category', ''),
                brand=item.get('brand', ''),
                price=item.get('price') or Decimal('0.00'),
                currency=item.get('currency', 'USD'),
                item_url=item.get('item_url', ''),
                image_url=item.get('image_url', ''),
                condition=item.get('condition', ''),
                seller_username=item.get('seller_username', ''),
                seller_feedback_score=item.get('seller_feedback_score') or 0,
                seller_feedback_percent=item.get('seller_feedback_percent') or 0,
                rating=item.get('rating') or 0,
                review_count=item.get('review_count') or 0,
                estimated_orders=item.get('estimated_orders') or 0,
                trend_score=item.get('trend_score') or 0,
                commercial_score=item.get('commercial_score') or 0,
                raw_data=item.get('raw_data') or {},
            ))

    recent_searches = SearchQuery.objects.all()[:5]
    return render(request, 'discovery/opportunity_search.html', {
        'form': form,
        'search_query': search_query,
        'discovered_products': discovered_products,
        'recent_searches': recent_searches,
    })


def search_results(request, pk):
    search_query = get_object_or_404(SearchQuery, pk=pk)
    discovered_products = search_query.products.all()
    return render(request, 'discovery/search_results.html', {
        'search_query': search_query,
        'discovered_products': discovered_products,
    })


def analyze_opportunity(request, pk):
    discovered = get_object_or_404(DiscoveredProduct, pk=pk)

    product = Product.objects.create(
        name=discovered.title[:200],
        category=discovered.category or discovered.search_query.category or 'eBay',
        brand=discovered.brand or discovered.seller_username or 'eBay',
        current_price=discovered.price,
        cost=None,
        discount_percent=0,
        rating=discovered.rating or 0,
        review_count=discovered.review_count or 0,
        # Pentru produse API, aceste date pot lipsi; pentru CSV fallback există valori mai bogate.
        views=max(discovered.estimated_orders * 8, discovered.review_count * 12, 0),
        add_to_cart=max(discovered.estimated_orders * 2, discovered.review_count * 2, 0),
        sales_volume=discovered.estimated_orders or 0,
        stock_level=50,
        conversion_rate=4.0 if discovered.estimated_orders else 0,
        margin_percent=25,
        season='normal',
    )

    probability, label, price, explanation = predict_product(product)
    explanation['sursa_oportunitate'] = discovered.source
    explanation['scor_comercial_discovery'] = discovered.commercial_score
    explanation['pret_platforma'] = float(discovered.price)
    explanation['moneda_platforma'] = discovered.currency

    PredictionRun.objects.create(
        product=product,
        success_probability=probability,
        success_label=label,
        recommended_price=price,
        model_name_classifier='RandomForestClassifier' if ml_artifacts_exist() else 'baseline_classifier',
        model_name_regressor='RandomForestRegressor' if ml_artifacts_exist() else 'baseline_regressor',
        explanation=explanation,
    )

    discovered.linked_product = product
    discovered.save(update_fields=['linked_product'])
    return redirect(reverse('prediction_detail', kwargs={'product_id': product.id}))
