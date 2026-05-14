from decimal import Decimal

from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from analytics.models import AnalysisRun
from products.models import Product
from predictions.models import PredictionRun
from predictions.services import predict_product, ml_artifacts_exist

from .forms import OpportunitySearchForm
from .models import DiscoveredProduct, SearchQuery
from .services import (
    discover_products,
    CATEGORY_CONVERSION_RATE,
    _normalize_category,
    _derive_views_and_cart,
    _detect_season,
)

# ─── Curs USD → RON ──────────────────────────────────────────────────────────
USD_TO_RON = Decimal('4.60')
EUR_TO_RON = Decimal('5.00')

# Prag avertisment predicție (model antrenat ~119 RON mediu)
PRICE_WARNING_THRESHOLD_RON = Decimal('300.00')


def _to_ron(price: Decimal, currency: str) -> Decimal:
    currency = currency.upper()
    if currency == 'USD':
        return (price * USD_TO_RON).quantize(Decimal('0.01'))
    if currency == 'EUR':
        return (price * EUR_TO_RON).quantize(Decimal('0.01'))
    return price.quantize(Decimal('0.01'))


def _short_name(title: str, max_len: int = 200) -> str:
    """Trunchiază titlul la primul virgulă — numele principal al produsului."""
    return title.split(',')[0].strip()[:max_len]


def _build_product_and_prediction(discovered: DiscoveredProduct, analysis_run: AnalysisRun):
    """
    Logică comună: creează Product + PredictionRun pentru un DiscoveredProduct.
    Returnează (product, prediction_run).
    """
    raw = discovered.raw_data or {}

    sales_volume_real = discovered.estimated_orders or raw.get('sales_volume_estimated', 0)
    discount_percent  = float(raw.get('discount_percent', 0) or 0)

    cat_key         = _normalize_category(discovered.category or '')
    conversion_rate = float(raw.get('conversion_rate') or CATEGORY_CONVERSION_RATE.get(cat_key, 3.4))
    review_count    = discovered.review_count or 0
    views_val, add_to_cart_val = _derive_views_and_cart(
        sales_volume_real, conversion_rate, review_count
    )

    season    = raw.get('season') or _detect_season(discovered.title, discovered.category or '')
    price_ron = _to_ron(discovered.price, discovered.currency)
    price_warning = price_ron > PRICE_WARNING_THRESHOLD_RON

    product = Product.objects.create(
        name=_short_name(discovered.title),
        category=discovered.category or 'Electronics',
        brand=discovered.brand or 'Unknown',
        current_price=price_ron,
        cost=None,
        discount_percent=discount_percent,
        rating=discovered.rating or 0,
        review_count=review_count,
        views=views_val,
        add_to_cart=add_to_cart_val,
        sales_volume=sales_volume_real,
        stock_level=50,
        conversion_rate=conversion_rate,
        margin_percent=25,
        season=season,
    )

    probability, label, price_recommended, explanation = predict_product(product)

    # ─── Îmbogățire explicație ────────────────────────────────────────────────
    explanation['sursa_oportunitate']           = discovered.source
    explanation['scor_oportunitate_investitor'] = discovered.commercial_score
    # Label pret sursa dinamic
    _price_label = {
        'amazon_api': 'pret_amazon_usd',
        'aliexpress_api': 'pret_aliexpress_usd',
        'ebay_api': 'pret_ebay_usd',
    }.get(discovered.source, 'pret_sursa_usd')
    explanation[_price_label]                   = float(discovered.price)
    explanation['pret_convertit_ron']           = float(price_ron)
    explanation['curs_usd_ron_folosit']         = float(USD_TO_RON)
    explanation['season_detectat']             = season
    explanation['views_derivate']              = views_val
    explanation['add_to_cart_derivat']         = add_to_cart_val
    explanation['conversion_rate_categorie']   = conversion_rate
    if price_warning:
        explanation['avertisment_pret'] = (
            f'Produsul are prețul ridicat ({float(price_ron):.0f} RON). '
            'Modelul ML a fost antrenat pe prețuri medii ~119 RON — '
            'predicția de preț recomandat poate fi mai puțin precisă.'
        )
    if raw.get('bsr'):
        explanation['amazon_bsr'] = raw['bsr']
    if sales_volume_real:
        explanation['volum_vanzari_estimat_bsr'] = sales_volume_real

    clf_name = 'LogisticRegression' if ml_artifacts_exist() else 'baseline_classifier'
    reg_name = 'GradientBoostingRegressor' if ml_artifacts_exist() else 'baseline_regressor'

    prediction_run = PredictionRun.objects.create(
        product=product,
        analysis_run=analysis_run,
        success_probability=probability,
        success_label=label,
        recommended_price=price_recommended,
        model_name_classifier=clf_name,
        model_name_regressor=reg_name,
        explanation=explanation,
    )

    discovered.linked_product = product
    discovered.save(update_fields=['linked_product'])

    return product, prediction_run


# ─── Views ───────────────────────────────────────────────────────────────────

def opportunity_search(request):
    form = OpportunitySearchForm(request.POST or None)
    search_query = None
    discovered_products = []

    if request.method == 'POST':
        # Citim toate valorile direct din POST — nu folosim form.save()
        # pentru a evita conflicte cu SOURCE_CHOICES din model
        valid_sources = ('api', 'aliexpress', 'ebay', 'csv')
        valid_top_n   = ('1', '3', '5', '10')

        raw_source = request.POST.get('data_source', '').strip()
        raw_top_n  = request.POST.get('top_n', '').strip()

        if raw_source not in valid_sources:
            raw_source = 'api'
        if raw_top_n not in valid_top_n:
            raw_top_n = '5'

        try:
            max_price  = request.POST.get('max_price') or None
            min_rating = float(request.POST.get('min_rating') or 0)
            min_reviews = int(request.POST.get('min_reviews') or 0)
        except Exception:
            max_price = None
            min_rating = 0.0
            min_reviews = 0

        search_query = SearchQuery.objects.create(
            keyword     = request.POST.get('keyword', '').strip(),
            category    = request.POST.get('category', '').strip(),
            max_price   = max_price,
            min_rating  = min_rating,
            min_reviews = min_reviews,
            top_n       = int(raw_top_n),
            data_source = raw_source,
        )

        result = discover_products(search_query)
        search_query.used_source = result.used_source
        search_query.status_message = result.status_message
        search_query.save(update_fields=['used_source', 'status_message'])

        for item in result.products:
            discovered_products.append(DiscoveredProduct.objects.create(
                search_query=search_query,
                source=item.get('source', 'amazon_api'),
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
    """
    Analiză individuală per produs → redirecționează la Fișa produs (XAI).
    """
    discovered = get_object_or_404(DiscoveredProduct, pk=pk)

    source_label = {
        'amazon_api':     AnalysisRun.SOURCE_DISCOVERY,
        'aliexpress_api': AnalysisRun.SOURCE_DISCOVERY,
        'ebay_api':       AnalysisRun.SOURCE_EBAY_API,
        'csv_fallback':   AnalysisRun.SOURCE_CSV_FALLBACK,
    }.get(discovered.source, AnalysisRun.SOURCE_DISCOVERY)

    short = _short_name(discovered.title)
    _platform_map = {
        'amazon_api': 'Amazon', 'aliexpress_api': 'AliExpress',
        'ebay_api': 'eBay', 'csv_fallback': 'Demo',
    }
    platform_label = _platform_map.get(discovered.source, 'Amazon')

    analysis_run = AnalysisRun.objects.create(
        title=f"Fișă produs {platform_label} — {short}"[:255],
        source_type=source_label,
        keyword=discovered.search_query.keyword,
        products_count=1,
        status=AnalysisRun.STATUS_COMPLETED,
        notes=(
            f"Produs individual: {short}. "
            f"Sursă: {discovered.source}."
        ),
    )

    product, _ = _build_product_and_prediction(discovered, analysis_run)
    analysis_run.refresh_counters()

    # → Fișa produs (pagina XAI)
    return redirect(reverse('prediction_detail', kwargs={'product_id': product.id}))


def analyze_batch(request, pk):
    """
    Analiză lot complet (toate produsele din căutare) → redirecționează la Raportul BI lot.
    """
    search_query  = get_object_or_404(SearchQuery, pk=pk)
    all_discovered = list(search_query.products.all())

    if not all_discovered:
        return redirect(reverse('discovery_search_results', kwargs={'pk': pk}))

    keyword  = search_query.keyword or 'descoperire automată'
    top_n    = search_query.top_n or len(all_discovered)

    analysis_run = AnalysisRun.objects.create(
        title=f"Raport lot · {keyword} · Top {top_n}"[:255],
        source_type=AnalysisRun.SOURCE_DISCOVERY,
        keyword=keyword,
        products_count=len(all_discovered),
        status=AnalysisRun.STATUS_COMPLETED,
        notes=(
            f"Analiză lot pentru {len(all_discovered)} produse "
            f"din căutarea: \"{keyword}\". Sursă: {all_discovered[0].source}."
        ),
    )

    for discovered in all_discovered:
        try:
            _build_product_and_prediction(discovered, analysis_run)
        except Exception:
            # Continuă cu restul produselor dacă unul eșuează
            continue

    analysis_run.refresh_counters()

    # → Raport BI lot
    return redirect(reverse('analysis_run_detail', kwargs={'pk': analysis_run.pk}))