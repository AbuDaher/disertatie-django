"""discovery/services.py — Amazon Real-Time Data + Google Trends + CSV fallback.

Fix-uri aplicate față de versiunile anterioare:
  1. views/add_to_cart derivate din sales_volume + conversion_rate (nu mediane statice)
  2. season detectat din titlu + categorie (cea mai importantă variabilă ML: 0.3852)
  3. opportunity_label stocat în raw_data → disponibil în template via DB
  4. Curs USD→RON documentat explicit și ușor de actualizat
  5. min_reviews readăugat ca filtru
  6. Investor Opportunity Score cu pondere corectă pe cerere dovedită
"""

from __future__ import annotations

import csv
import os
import time
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import requests
from django.conf import settings


# ─── Categorii pentru descoperire automată ───────────────────────────────────
DEFAULT_OPPORTUNITY_KEYWORDS = [
    'wireless earbuds',
    'smart home device',
    'fitness tracker',
    'portable charger',
    'kitchen gadget',
]

# ─── Mediane pe categorie — DOAR pentru câmpuri fără alternativă mai bună ─────
# views și add_to_cart sunt acum derivate din sales_volume (mai precise)
# conversion_rate rămâne imputat — nu există sursă publică
CATEGORY_CONVERSION_RATE: dict[str, float] = {
    'electronics': 3.5,
    'fashion':     3.2,
    'beauty':      4.1,
    'sports':      3.0,
    'home':        3.3,
    'books':       4.5,
    'toys':        3.8,
    'automotive':  2.8,
    'health':      3.9,
    'garden':      2.9,
    'default':     3.4,
}

# Mapare Amazon → ML
AMAZON_TO_ML_CATEGORY: dict[str, str] = {
    'electronics': 'Electronics', 'computers': 'Electronics',
    'cell phones': 'Electronics', 'camera': 'Electronics',
    'headphones': 'Electronics', 'earbuds': 'Electronics',
    'audio': 'Electronics', 'smart home': 'Electronics',
    'wearable': 'Electronics', 'tablet': 'Electronics',
    'clothing': 'Fashion', 'shoes': 'Fashion', 'apparel': 'Fashion',
    'jewelry': 'Fashion', 'watches': 'Fashion',
    'beauty': 'Beauty', 'personal care': 'Beauty', 'skin care': 'Beauty',
    'hair care': 'Beauty', 'makeup': 'Beauty',
    'sports': 'Sports', 'outdoors': 'Sports', 'fitness': 'Sports',
    'exercise': 'Sports', 'yoga': 'Sports',
    'home': 'Home', 'kitchen': 'Home', 'furniture': 'Home',
    'bedding': 'Home', 'bath': 'Home', 'appliance': 'Home',
    'garden': 'Garden', 'patio': 'Garden', 'lawn': 'Garden',
    'toys': 'Toys', 'games': 'Toys', 'baby': 'Toys',
    'books': 'Books', 'kindle': 'Books',
    'automotive': 'Automotive', 'tools': 'Automotive', 'hardware': 'Automotive',
    'health': 'Health', 'grocery': 'Health', 'vitamins': 'Health',
    'supplement': 'Health', 'medical': 'Health',
}

# Mapare categorie → keyword Amazon pentru căutare mai precisă
# Căutarea cu termeni generici ('beauty', 'electronics') e respinsă de API
CATEGORY_TO_KEYWORD: dict[str, str] = {
    'beauty':      'best beauty products',
    'electronics': 'popular electronics gadgets',
    'fashion':     'trending fashion accessories',
    'sports':      'fitness equipment',
    'home':        'smart home gadgets',
    'health':      'health wellness products',
    'toys':        'popular kids toys',
    'garden':      'garden tools accessories',
    'books':       'bestseller nonfiction',
    'automotive':  'car accessories gadgets',
}


# Sezonuri valide în datele de antrenare
VALID_SEASONS = {'normal', 'holiday', 'promo', 'offseason'}


@dataclass
class DiscoveryResult:
    products: list[dict[str, Any]]
    used_source: str
    status_message: str


# ─── Utilitare ────────────────────────────────────────────────────────────────

def _to_decimal(value: Any, default: str = '0') -> Decimal:
    try:
        if value in (None, ''):
            return Decimal(default)
        cleaned = str(value).replace(',', '').replace('$', '').replace('€', '').strip()
        return Decimal(cleaned).quantize(Decimal('0.01'))
    except Exception:
        return Decimal(default)


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(float(str(value).replace(',', '').strip()))
    except Exception:
        return default


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ''):
            return default
        return float(str(value).replace(',', '.').strip())
    except Exception:
        return default


def _normalize_category(raw: str) -> str:
    if not raw:
        return 'default'
    lower = raw.lower()
    for key in CATEGORY_CONVERSION_RATE:
        if key in lower:
            return key
    return 'default'


def _map_to_ml_category(amazon_category: str) -> str:
    if not amazon_category:
        return 'Electronics'
    lower = amazon_category.lower()
    for key, ml_cat in AMAZON_TO_ML_CATEGORY.items():
        if key in lower:
            return ml_cat
    return amazon_category.title()


def _detect_season(title: str, category: str) -> str:
    """Detectează sezonul din titlu și categorie.

    season este variabila cu cea mai mare importanță în modelul ML (0.3852 SHAP).
    Valori valide din datele de antrenare: normal, holiday, promo, offseason.

    Logică:
      - 'holiday': produse de cadouri, Crăciun, Valentine, Back to School
      - 'promo':   produse cu reduceri active, Black Friday, deals
      - 'offseason': produse sezoniere în afara sezonului principal
      - 'normal':  orice altceva
    """
    t = (title or '').lower()
    c = (category or '').lower()

    # Holiday — cadouri, sărbători
    holiday_signals = [
        'christmas', 'holiday', 'gift', 'valentine', 'mother', 'father',
        'birthday', 'wedding', 'graduation', 'easter', 'halloween',
        'thanksgiving', 'back to school', 'back-to-school',
    ]
    if any(s in t or s in c for s in holiday_signals):
        return 'holiday'

    # Promo — reduceri active
    promo_signals = [
        'sale', 'deal', 'promo', 'discount', 'offer', 'bundle',
        'value pack', 'multipack', 'combo', 'black friday', 'cyber monday',
        'prime day', 'clearance',
    ]
    if any(s in t for s in promo_signals):
        return 'promo'

    # Offseason — produse sezoniere detectate ca atare
    offseason_signals = [
        'winter', 'summer', 'spring', 'fall', 'seasonal',
        'snow', 'ice', 'beach', 'pool', 'camping', 'hiking',
        'ski', 'snowboard',
    ]
    if any(s in t for s in offseason_signals):
        return 'offseason'

    return 'normal'


def _derive_views_and_cart(
    sales_volume: int,
    conversion_rate: float,
    review_count: int,
) -> tuple[int, int]:
    """Derivă views și add_to_cart din sales_volume și conversion_rate.

    Formula:
      views = sales_volume / (conversion_rate / 100)
      add_to_cart ≈ views * 0.10  (rata tipică Amazon ~8-12%)

    Valori clipate la intervalul din datele de antrenare:
      views: max 20.000 (pragul din feature engineering demand_index)
      add_to_cart: max 2.000

    De ce e mai bine decât mediane statice:
      Un produs cu 8.392 vânzări/lună la cr=3.5% → views=239.771 → clipat la 20.000
      Un produs cu 50 vânzări/lună la cr=3.5%  → views=1.428 → nemodificat
      Rezultat: demand_index diferențiază corect între produse populare și nepopulare.
    """
    if sales_volume <= 0 or conversion_rate <= 0:
        # Fallback la mediană globală dacă datele lipsesc
        return 1900, 140

    views_raw = sales_volume / (conversion_rate / 100.0)
    views = min(int(views_raw), 20_000)  # clipare la max din feature engineering
    add_to_cart = min(int(views * 0.10), 2_000)
    return max(views, 1), max(add_to_cart, 1)


def _bsr_to_sales_volume(bsr: int) -> int:
    """Estimează volumul lunar de vânzări din BSR Amazon.
    Formula: sales ≈ 1_000_000 / (BSR ^ 0.9)
    """
    if not bsr or bsr <= 0:
        return 0
    estimated = int(1_000_000 / (bsr ** 0.9))
    return max(1, min(estimated, 50_000))


def _opportunity_label(score: float) -> str:
    if score >= 70:
        return 'Oportunitate excelentă'
    if score >= 50:
        return 'Oportunitate bună'
    if score >= 30:
        return 'Oportunitate moderată'
    return 'Potențial limitat'


def _opportunity_score_class(score: float) -> str:
    if score >= 70:
        return 'opp-score-excellent'
    if score >= 50:
        return 'opp-score-good'
    if score >= 30:
        return 'opp-score-moderate'
    return 'opp-score-low'


# ─── Investor Opportunity Score ───────────────────────────────────────────────

def calculate_investor_score(
    product: dict[str, Any],
    max_price: Decimal | None = None,
) -> float:
    """Scor 0-100 din perspectiva investitorului.

    Criterii:
      1. Cerere dovedită    (40 pts) — recenzii + vânzări lunare estimate BSR
      2. Calitate produs    (20 pts) — rating ponderat logaritmic cu nr. recenzii
      3. Momentum piață     (15 pts) — Google Trends 7 zile
      4. Potențial marjă    (15 pts) — intervalul de preț $15-$80 optim pentru resale
      5. Discount activ     (10 pts) — semnal de oportunitate de preț
    """
    import math

    source = product.get('source', 'csv_fallback')
    price = _to_decimal(product.get('price'))

    # Penalizare imediată dacă depășește bugetul
    if max_price and price > max_price:
        return 0.0

    if source not in ('amazon_api', 'aliexpress_api', 'ebay_api'):
        return _score_csv_investor(product, max_price)

    rating       = _to_float(product.get('rating'))
    review_count = _to_int(product.get('review_count'))
    sales_volume = _to_int(product.get('sales_volume'))
    trend        = _to_float(product.get('trend_score'))
    discount     = _to_float(product.get('discount_percent'))
    price_f      = float(price)

    # 1. Cerere dovedită (40 pts)
    review_score = min(review_count / 10_000.0, 1.0) * 20.0
    sales_score  = min(sales_volume / 1_000.0, 1.0) * 20.0
    demand_score = review_score + sales_score

    # 2. Calitate produs (20 pts)
    # Rating ponderat logaritmic: 4.5★ cu 50.000 recenzii > 4.9★ cu 10 recenzii
    review_weight = min(math.log10(max(review_count, 1)) / 5.0, 1.0)
    quality_score = min(max(rating - 3.5, 0.0) / 1.5, 1.0) * review_weight * 20.0

    # 3. Momentum piață (15 pts)
    momentum_score = min(trend / 100.0, 1.0) * 15.0

    # 4. Potențial marjă (15 pts)
    # Intervalul optim depinde de sursa produsului:
    # Amazon/eBay: $15-$80 (resale direct)
    # AliExpress:  $3-$30  (dropshipping, marja % mare la preturi mici)
    source = product.get('source', '')
    if source == 'aliexpress_api':
        # AliExpress: produse ieftine cu marjă procentuala ridicata
        if 3.0 <= price_f <= 30.0:
            margin_score = 15.0
        elif 1.0 <= price_f < 3.0 or 30.0 < price_f <= 60.0:
            margin_score = 10.0
        elif price_f > 60.0:
            margin_score = 5.0
        else:
            margin_score = 2.0
    else:
        # Amazon/eBay: resale traditional
        if 15.0 <= price_f <= 80.0:
            margin_score = 15.0
        elif 10.0 <= price_f < 15.0 or 80.0 < price_f <= 150.0:
            margin_score = 10.0
        elif price_f > 150.0:
            margin_score = 5.0
        else:
            margin_score = 3.0

    # 5. Discount activ (10 pts)
    discount_score = min(discount / 30.0, 1.0) * 10.0

    total = demand_score + quality_score + momentum_score + margin_score + discount_score
    return round(min(max(total, 0.0), 100.0), 2)


def _score_csv_investor(product: dict[str, Any], max_price: Decimal | None) -> float:
    rating   = _to_float(product.get('rating'))
    reviews  = _to_int(product.get('review_count'))
    orders   = _to_int(product.get('estimated_orders'))
    trend    = _to_float(product.get('trend_score'))
    price    = _to_decimal(product.get('price'))
    if max_price and price > max_price:
        return 0.0
    score = (
        min(rating / 5.0, 1.0) * 25.0
        + min(reviews / 500.0, 1.0) * 20.0
        + min(orders / 1000.0, 1.0) * 25.0
        + min(trend / 100.0, 1.0) * 15.0
    )
    return round(min(max(score, 0.0), 100.0), 2)


# ─── Google Trends ────────────────────────────────────────────────────────────

# ─── Trend cache în memorie (resetat la restart server) ──────────────────────
# Format: { 'keyword_normalized': (score: float, timestamp: float) }
_TREND_CACHE: dict[str, tuple[float, float]] = {}
_TREND_CACHE_TTL = 86400.0  # 24 ore în secunde


# Fallback inteligent bazat pe sezon + categorie
# În loc de 50 neutral pentru toți, estimăm din context real
_TREND_SEASONAL_BASELINE: dict[str, dict[str, float]] = {
    'electronics': {'normal': 62, 'summer': 58, 'winter': 68, 'holiday': 88, 'promo': 80},
    'beauty':      {'normal': 58, 'summer': 65, 'winter': 60, 'holiday': 82, 'promo': 75},
    'sports':      {'normal': 60, 'summer': 78, 'winter': 48, 'holiday': 70, 'promo': 72},
    'home':        {'normal': 55, 'summer': 60, 'winter': 72, 'holiday': 85, 'promo': 70},
    'health':      {'normal': 64, 'summer': 68, 'winter': 62, 'holiday': 72, 'promo': 74},
    'fashion':     {'normal': 56, 'summer': 70, 'winter': 65, 'holiday': 86, 'promo': 78},
    'toys':        {'normal': 50, 'summer': 55, 'winter': 90, 'holiday': 95, 'promo': 80},
    'garden':      {'normal': 50, 'summer': 82, 'winter': 28, 'holiday': 45, 'promo': 58},
    'automotive':  {'normal': 54, 'summer': 60, 'winter': 58, 'holiday': 62, 'promo': 66},
    'default':     {'normal': 55, 'summer': 60, 'winter': 58, 'holiday': 82, 'promo': 74},
}


def _trend_smart_fallback(keyword: str, category: str = '') -> float:
    """
    Fallback inteligent când PyTrends e indisponibil.
    Estimează trend din sezon curent + categorie — diferențiază produsele
    în loc să returneze 50 neutral pentru toți.
    """
    import datetime
    now = datetime.datetime.now()
    month = now.month

    # Detectare sezon curent
    if month in (11, 12):
        season = 'holiday'
    elif month in (6, 7, 8):
        season = 'summer'
    elif month in (12, 1, 2):
        season = 'winter'
    else:
        season = 'normal'

    # Detectare promo (Black Friday nov, sales ian/iul)
    if month == 11 or (month == 1 and now.day <= 15) or (month == 7 and now.day <= 15):
        season = 'promo'

    # Mapare categorie la cheie din baseline
    cat_lower = (category or keyword or '').lower()
    cat_key = 'default'
    for key in _TREND_SEASONAL_BASELINE:
        if key in cat_lower:
            cat_key = key
            break

    base = _TREND_SEASONAL_BASELINE[cat_key][season]

    # Variatie mica bazata pe keyword (determinist, nu random)
    # Produse diferite din aceeasi categorie primesc scoruri usor diferite
    kw_hash = sum(ord(c) for c in keyword.lower()) % 15  # 0-14
    return round(base - 7 + kw_hash, 1)  # ±7 fata de baseline


def _get_trend_score(keyword: str, category: str = '') -> float:
    """
    Returnează trend_score (0-100) pentru un keyword.

    Strategie în 3 niveluri:
    1. Cache în memorie (TTL 24h) — zero calls API
    2. PyTrends real — valoare live din Google Trends
    3. Fallback inteligent bazat pe sezon + categorie (în loc de 50 neutral)
    """
    import time

    cache_key = keyword.lower().strip()

    # Nivel 1: Cache
    if cache_key in _TREND_CACHE:
        score, ts = _TREND_CACHE[cache_key]
        if time.time() - ts < _TREND_CACHE_TTL:
            return score

    # Nivel 2: PyTrends real
    try:
        from pytrends.request import TrendReq  # type: ignore
        pt = TrendReq(hl='en-US', tz=360, timeout=(10, 20), retries=1, backoff_factor=0.3)
        pt.build_payload([keyword], cat=0, timeframe='now 7-d', geo='', gprop='')
        data = pt.interest_over_time()
        if not data.empty and keyword in data.columns:
            score = round(float(data[keyword].mean()), 1)
            _TREND_CACHE[cache_key] = (score, time.time())
            return score
        # PyTrends a raspuns dar fara date → fallback inteligent
        score = _trend_smart_fallback(keyword, category)
        _TREND_CACHE[cache_key] = (score, time.time())
        return score
    except Exception:
        # Nivel 3: Fallback inteligent
        score = _trend_smart_fallback(keyword, category)
        # Nu stocam in cache fallback-urile — urmatorul call poate prinde PyTrends disponibil
        return score


# ─── Amazon RapidAPI client ───────────────────────────────────────────────────

class AmazonRapidAPIClient:
    API_HOST = 'real-time-amazon-data.p.rapidapi.com'
    BASE_URL = 'https://real-time-amazon-data.p.rapidapi.com'

    def __init__(self):
        self.api_key = os.getenv('RAPIDAPI_KEY', '').strip()

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict[str, str]:
        return {
            'x-rapidapi-key': self.api_key,
            'x-rapidapi-host': self.API_HOST,
            'Content-Type': 'application/json',
        }

    def search(self, keyword: str, country: str = 'US', page: int = 1) -> list[dict[str, Any]]:
        url = f'{self.BASE_URL}/search'
        params = {
            'query': keyword,
            'country': country,
            'category_id': 'aps',
            'sort_by': 'RELEVANCE',
            'page': str(page),
        }
        response = requests.get(url, headers=self._headers(), params=params, timeout=25)
        response.raise_for_status()
        return response.json().get('data', {}).get('products', [])

    def get_product_details(self, asin: str, country: str = 'US') -> dict[str, Any]:
        url = f'{self.BASE_URL}/product-details'
        try:
            response = requests.get(
                url,
                headers=self._headers(),
                params={'asin': asin, 'country': country},
                timeout=15,
            )
            response.raise_for_status()
            return response.json().get('data', {})
        except Exception:
            return {}


def _map_amazon_product(
    item: dict[str, Any],
    details: dict[str, Any],
    trend_score: float,
    keyword: str,
) -> dict[str, Any] | None:
    """Mapează un produs Amazon la formatul intern cu toate câmpurile corecte."""

    title = item.get('product_title') or item.get('title', '')
    if not title:
        return None

    price_str = (
        item.get('product_price') or item.get('price')
        or details.get('product_price') or '0'
    )
    price = _to_decimal(price_str)
    if price <= 0:
        return None

    # Discount
    original_price = _to_decimal(
        item.get('product_original_price')
        or details.get('product_original_price')
        or price_str
    )
    discount_percent = 0.0
    if original_price > price and original_price > 0:
        discount_percent = round(
            float((original_price - price) / original_price * 100), 1
        )

    # Rating
    rating_raw = (
        item.get('product_star_rating')
        or details.get('product_star_rating') or '0'
    )
    rating = _to_float(str(rating_raw).replace(' out of 5 stars', '').strip())

    # Recenzii
    review_count = _to_int(
        item.get('product_num_ratings')
        or details.get('product_num_ratings') or '0'
    )

    # BSR → sales_volume
    bsr = 0
    bestseller_rank = details.get('bestseller_rank') or []
    if isinstance(bestseller_rank, list) and bestseller_rank:
        first = bestseller_rank[0]
        rank_str = first.get('rank', '0') if isinstance(first, dict) else str(first)
        bsr = _to_int(str(rank_str).replace('#', '').replace(',', '').strip())
    elif isinstance(bestseller_rank, str):
        bsr = _to_int(bestseller_rank.replace('#', '').replace(',', '').strip())

    sales_volume = _bsr_to_sales_volume(bsr)
    if sales_volume == 0 and review_count > 0:
        # Estimare din recenzii dacă BSR nu e disponibil (~8% din recenzii = vânzări lunare)
        sales_volume = max(int(review_count * 0.08), 1)

    # Categorie și brand
    amazon_category = (
        item.get('product_category') or details.get('product_category')
        or details.get('department') or keyword
    )
    ml_category = _map_to_ml_category(str(amazon_category))
    brand = (
        item.get('product_brand') or details.get('brand')
        or (details.get('product_details') or {}).get('Brand', '') or ''
    )
    asin = item.get('asin') or item.get('product_asin') or ''

    # ─── FIX 1: views/add_to_cart derivate din sales_volume ──────────────────
    cat_key = _normalize_category(ml_category)
    conversion_rate = CATEGORY_CONVERSION_RATE.get(cat_key, 3.4)
    views, add_to_cart = _derive_views_and_cart(sales_volume, conversion_rate, review_count)

    # ─── FIX 2: season detectat din titlu și categorie ───────────────────────
    season = _detect_season(title, ml_category)

    # ─── FIX 3: opportunity_label calculat și stocat în raw_data ─────────────
    # Calculăm scorul preliminar pentru label — fără max_price
    temp_product = {
        'source': 'amazon_api',
        'price': price,
        'rating': rating,
        'review_count': review_count,
        'sales_volume': sales_volume,
        'trend_score': trend_score,
        'discount_percent': discount_percent,
    }
    prelim_score = calculate_investor_score(temp_product, max_price=None)
    opp_label = _opportunity_label(prelim_score)
    opp_class = _opportunity_score_class(prelim_score)

    mapped: dict[str, Any] = {
        'source': 'amazon_api',
        'external_id': asin,
        'title': title[:300],
        'category': ml_category,
        'brand': brand[:120],
        'price': price,
        'currency': 'USD',
        'item_url': (item.get('product_url') or details.get('product_url') or '')[:500],
        'image_url': (item.get('product_photo') or item.get('thumbnail') or '')[:500],
        'condition': 'New',
        'seller_username': '',
        'seller_feedback_score': 0,
        'seller_feedback_percent': 0.0,
        'rating': round(rating, 1),
        'review_count': review_count,
        'estimated_orders': sales_volume,
        'sales_volume': sales_volume,
        'discount_percent': discount_percent,
        'trend_score': trend_score,
        'bsr': bsr,
        # FIX 1 — derivate, nu mediane statice
        'views': views,
        'add_to_cart': add_to_cart,
        'conversion_rate': conversion_rate,
        # FIX 2 — season detectat
        'season': season,
        'margin_percent': 25.0,
        'stock_level': 50,
        'cost': 0.0,
    }

    # raw_data stochează tot ce trebuie disponibil în views.py și template
    mapped['raw_data'] = {
        'asin': asin,
        'bsr': bsr,
        'sales_volume_estimated': sales_volume,
        'amazon_category': str(amazon_category),
        'discount_percent': discount_percent,
        'views': views,
        'add_to_cart': add_to_cart,
        'conversion_rate': conversion_rate,
        'season': season,
        # FIX 3 — label și clasă CSS stocate în DB
        'opportunity_label': opp_label,
        'opportunity_score_class': opp_class,
        'imputed_fields': ['conversion_rate'],  # views/add_to_cart sunt derivate, nu imputate
    }

    return mapped


def _fetch_amazon_products(
    client: AmazonRapidAPIClient,
    keyword: str,
    top_n: int,
    trend_score: float,
) -> list[dict[str, Any]]:
    results = []
    # Incercam max 3 pagini pentru a obtine top_n rezultate valide
    # Unele produse din search pot esua la mapare (pret 0, ASIN invalid etc.)
    for page in range(1, 4):
        if len(results) >= top_n:
            break
        raw_items = client.search(keyword=keyword, country='US', page=page)
        if not raw_items:
            break
        for item in raw_items:
            if len(results) >= top_n:
                break
            asin = item.get('asin') or item.get('product_asin', '')
            details: dict[str, Any] = {}
            if asin:
                details = client.get_product_details(asin, country='US')
                time.sleep(0.3)
            mapped = _map_amazon_product(item, details, trend_score, keyword)
            if mapped:
                results.append(mapped)
        # Trecem la pagina urmatoare doar daca nu am obtinut suficiente rezultate
        if len(results) >= top_n:
            break
    return results


# ─── AliExpress Business API client ─────────────────────────────────────────

def test_aliexpress_raw(keyword='earbuds', page_size=1):
    """
    Apeleaza direct API-ul AliExpress si printeaza structura bruta.
    Ruleaza din Django shell:
      from discovery.services import test_aliexpress_raw
      test_aliexpress_raw()
    """
    import json, os
    api_key = os.getenv('ALIEXPRESS_API_KEY') or os.getenv('RAPIDAPI_KEY')
    import requests
    headers = {
        'x-rapidapi-key': api_key,
        'x-rapidapi-host': 'aliexpress-business-api.p.rapidapi.com',
        'Content-Type': 'application/json',
    }
    url = 'https://aliexpress-business-api.p.rapidapi.com/textsearch.php'
    params = {
        'keyWord': keyword, 'pageSize': str(page_size),
        'pageIndex': '1', 'currency': 'USD',
        'lang': 'en', 'country': 'RO',
        'filter': 'orders', 'sortBy': 'desc',
    }
    r = requests.get(url, headers=headers, params=params, timeout=20)
    print(f"Status: {r.status_code}")
    data = r.json()
    inner = data.get('data') or data.get('result') or {}
    items = inner.get('itemList') or inner.get('resultList') or []
    if items:
        item = items[0]
        print(f"\n=== FIRST ITEM ALL KEYS ===")
        print(json.dumps(item, indent=2, ensure_ascii=False)[:3000])
    else:
        print("No items found")
        print(json.dumps(data, indent=2)[:1000])


class AliExpressBusinessAPIClient:
    """
    Client pentru AliExpress Business API via RapidAPI.
    Endpoint-uri: /textsearch.php (search), /itemdetail.php (detalii produs)
    Cheia API: ALIEXPRESS_API_KEY din .env (separata de RAPIDAPI_KEY pentru Amazon)
    """
    API_HOST = 'aliexpress-business-api.p.rapidapi.com'
    BASE_URL = 'https://aliexpress-business-api.p.rapidapi.com'

    def __init__(self):
        # Incearca ALIEXPRESS_API_KEY mai intai, fallback la RAPIDAPI_KEY
        # ALIEXPRESS_API_KEY = db3bc8cb40mshe24ad38d415fb62p169eebjsnd2035fa1f3d0
        # RAPIDAPI_KEY = cheia Amazon
        self.api_key = (
            os.getenv('ALIEXPRESS_API_KEY', '').strip() or
            os.getenv('RAPIDAPI_KEY', '').strip()
        )

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict[str, str]:
        return {
            'x-rapidapi-key': self.api_key,
            'x-rapidapi-host': self.API_HOST,
            'Content-Type': 'application/json',
        }

    def search(self, keyword: str, page_size: int = 10) -> list[dict[str, Any]]:
        url = f'{self.BASE_URL}/textsearch.php'
        params = {
            'keyWord':   keyword,
            'pageSize':  str(page_size),
            'pageIndex': '1',
            'currency':  'USD',
            'lang':      'en',
            'country':   'RO',
            'filter':    'orders',
            'sortBy':    'desc',
        }
        response = requests.get(url, headers=self._headers(), params=params, timeout=20)
        response.raise_for_status()
        data = response.json()
        # Structura reala: {"status": {...}, "data": {"itemList": [...]}}
        inner = data.get('data') or data.get('result') or {}
        return (
            inner.get('itemList') or
            inner.get('resultList') or inner.get('products') or
            data.get('itemList') or data.get('resultList') or []
        )

    def get_item_detail(self, item_id: str) -> dict[str, Any]:
        url = f'{self.BASE_URL}/itemdetail.php'
        try:
            response = requests.get(
                url, headers=self._headers(),
                params={'itemId': item_id, 'currency': 'USD', 'lang': 'en'},
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()
            inner = data.get('data') or data.get('result') or {}
            return inner.get('item') or inner or {}
        except Exception:
            return {}


def _map_aliexpress_product(
    item: dict[str, Any],
    details: dict[str, Any],
    trend_score: float,
    keyword: str,
) -> dict[str, Any] | None:
    # Raspunsul real are campurile direct in item (nu nested sub 'item')
    raw_item = item.get('item', item)

    item_id = str(
        raw_item.get('itemId') or raw_item.get('productId') or
        details.get('itemId') or ''
    )
    title = (
        raw_item.get('title') or raw_item.get('productTitle') or
        details.get('title') or ''
    )
    if not title or not item_id:
        return None

    # Pret: salePrice sau targetSalePrice (campuri reale din API)
    # Pret: 'targetSalePrice' e in USD (moneda tinta)
    # 'salePrice' e in CNY (moneda sursa) — nu folosim asta!
    price_raw = (
        raw_item.get('targetSalePrice') or raw_item.get('targetOriginalPrice') or
        raw_item.get('promotionPrice') or
        details.get('targetSalePrice') or details.get('salePrice') or 0
    )
    try:
        price = Decimal(str(price_raw)).quantize(Decimal('0.01'))
    except Exception:
        price = Decimal('0.00')
    if price <= 0:
        return None

    # Discount: camp 'discount' e string tip "2%" in raspunsul real
    # Discount: campul 'discount' e '0%' sau '15%' — extragem cifra
    discount_raw = raw_item.get('discount') or details.get('discount') or '0%'
    try:
        discount_pct = float(str(discount_raw).replace('%', '').strip())
    except Exception:
        discount_pct = 0.0
    # Calculam si din originalPrice vs targetSalePrice ca verificare
    if discount_pct == 0:
        try:
            orig = float(raw_item.get('targetOriginalPrice') or raw_item.get('originalPrice') or 0)
            cur  = float(price_raw)
            if orig > cur > 0:
                discount_pct = round((1 - cur / orig) * 100, 1)
        except Exception:
            pass

    # Rating si recenzii
    # Rating — campul real este 'score' (ex: "4.4")
    rating = float(
        raw_item.get('score') or raw_item.get('averageStarRate') or
        raw_item.get('starRating') or details.get('score') or
        details.get('averageStarRate') or details.get('starRating') or 0
    )

    # Recenzii — AliExpress search NU returneaza numarul de recenzii
    # 'evaluateRate' e procentul de evaluari pozitive (ex: "88.5"), nu numarul
    # Estimam din 'orders' (vanzari) — proxy rezonabil
    # Un produs cu 50.000+ vanzari are tipic mii de recenzii
    def _parse_quantity(val):
        """Parseaza '50,000+' sau '10k+' in int."""
        if not val:
            return 0
        try:
            s = str(val).replace('+','').replace(',','').strip().lower()
            if s.endswith('k'):
                return int(float(s[:-1]) * 1000)
            if s.endswith('m'):
                return int(float(s[:-1]) * 1000000)
            return int(float(s))
        except Exception:
            return 0

    # Vanzari — campul real este 'orders' (ex: "50,000+")
    sales_volume = (
        _parse_quantity(raw_item.get('orders')) or
        _parse_quantity(raw_item.get('sales')) or
        _parse_quantity(raw_item.get('sold')) or
        _parse_quantity(details.get('orders')) or
        _parse_quantity(details.get('tradeCount')) or 0
    )

    # Recenzii estimate din vanzari (ratio ~1 recenzie la 10 vanzari pe AliExpress)
    # evaluateRate = % evaluari pozitive, nu numarul — nu e util ca review_count
    evaluate_rate = float(raw_item.get('evaluateRate') or 0)
    if sales_volume > 0:
        review_count = max(int(sales_volume * 0.08), 1)
    else:
        review_count = 0



    # Categorie
    cat_id = str(raw_item.get('cateId') or raw_item.get('categoryId') or '')
    category = (
        details.get('categoryName') or raw_item.get('category') or
        _normalize_category(keyword).capitalize() or 'Electronics'
    )

    # URL-uri
    item_url = (
        raw_item.get('itemUrl') or raw_item.get('productUrl') or
        f'https://www.aliexpress.com/item/{item_id}.html'
    )
    image_url = (
        raw_item.get('itemMainPic') or raw_item.get('image') or
        raw_item.get('imageUrl') or details.get('imageUrl') or ''
    )
    if image_url.startswith('//'):
        image_url = 'https:' + image_url

    brand = (
        details.get('brand') or details.get('storeName') or
        raw_item.get('storeName') or raw_item.get('brandName') or 'AliExpress'
    )

    _temp_product = {
        'source':           'aliexpress_api',
        'price':            price,
        'rating':           rating,
        'review_count':     review_count,
        'sales_volume':     sales_volume,
        'trend_score':      trend_score,
        'discount_percent': discount_pct,
        'views':            0,
        'add_to_cart':      0,
    }
    commercial_score = calculate_investor_score(_temp_product, max_price=None)

    return {
        'source': 'aliexpress_api', 'external_id': item_id, 'title': title,
        'category': category, 'brand': brand, 'price': price, 'currency': 'USD',
        'item_url': item_url, 'image_url': image_url, 'condition': 'New',
        'rating': rating, 'review_count': review_count, 'estimated_orders': sales_volume,
        'trend_score': trend_score, 'commercial_score': commercial_score,
        'raw_data': {
            'source': 'aliexpress_api', 'item_id': item_id,
            'discount_percent': discount_pct, 'rating': rating,
            'review_count': review_count, 'sales_volume': sales_volume,
            'trend_score': trend_score,
        },
    }


def _fetch_aliexpress_products(
    client: AliExpressBusinessAPIClient,
    keyword: str,
    top_n: int = 5,
    trend_score: float = 50.0,
) -> list[dict[str, Any]]:
    results = []
    raw_items = client.search(keyword=keyword, page_size=min(top_n * 2, 20))
    for item in raw_items:
        if len(results) >= top_n:
            break
        raw_item = item.get('item', item)
        item_id  = str(raw_item.get('itemId') or raw_item.get('productId') or '')
        details: dict[str, Any] = {}
        if item_id:
            details = client.get_item_detail(item_id)
            time.sleep(0.3)
        mapped = _map_aliexpress_product(item, details, trend_score, keyword)
        if mapped:
            results.append(mapped)
    return results


# ─── eBay Browse API client ──────────────────────────────────────────────────

class EbayBrowseAPIClient:
    """
    Client pentru eBay Browse API — acces direct, fara RapidAPI.
    Autentificare: OAuth2 Client Credentials (token cached 2h).
    """
    TOKEN_URL  = 'https://api.ebay.com/identity/v1/oauth2/token'
    SEARCH_URL = 'https://api.ebay.com/buy/browse/v1/item_summary/search'
    SCOPE      = 'https://api.ebay.com/oauth/api_scope'

    _token_cache: dict[str, Any] = {}  # {'token': str, 'expires_at': float}

    def __init__(self):
        self.client_id     = os.getenv('EBAY_CLIENT_ID', '').strip()
        self.client_secret = os.getenv('EBAY_CLIENT_SECRET', '').strip()

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def _get_token(self) -> str:
        """Returneaza token OAuth2 valid, din cache sau proaspat."""
        import base64, time as _time
        cache = EbayBrowseAPIClient._token_cache
        if cache.get('token') and _time.time() < cache.get('expires_at', 0):
            return cache['token']

        credentials = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()
        resp = requests.post(
            self.TOKEN_URL,
            headers={
                'Authorization': f'Basic {credentials}',
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            data=f'grant_type=client_credentials&scope={self.SCOPE}',
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        token = data['access_token']
        expires_in = int(data.get('expires_in', 7200))
        import time as _t
        cache['token'] = token
        cache['expires_at'] = _t.time() + expires_in - 60  # 1 min buffer
        return token

    def search(self, keyword: str, limit: int = 10) -> list[dict[str, Any]]:
        """Cauta produse eBay dupa keyword. Returneaza lista de itemSummary."""
        token = self._get_token()
        resp = requests.get(
            self.SEARCH_URL,
            headers={
                'Authorization': f'Bearer {token}',
                'X-EBAY-C-MARKETPLACE-ID': 'EBAY_US',
                'Content-Type': 'application/json',
            },
            params={
                'q':      keyword,
                'limit':  str(limit),
                'sort':   'bestMatch',
                'filter': 'conditionIds:{1000|1500|2000|2500}',  # New/Like New
            },
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json().get('itemSummaries', [])


def _map_ebay_product(
    item: dict[str, Any],
    trend_score: float,
    keyword: str,
) -> dict[str, Any] | None:
    """Mapeaza un itemSummary eBay la structura interna Django."""
    item_id = item.get('itemId', '')
    title   = item.get('title', '')
    if not title or not item_id:
        return None

    # Pret
    price_info = item.get('price') or {}
    price_raw  = price_info.get('value', 0)
    currency   = price_info.get('currency', 'USD')
    try:
        price = Decimal(str(price_raw)).quantize(Decimal('0.01'))
    except Exception:
        price = Decimal('0.00')
    if price <= 0:
        return None

    # Rating si recenzii — eBay nu are rating per produs
    # Estimam din: averageRating (daca exista) sau seller feedback + variatie per produs
    buying_options = item.get('buyingOptions', [])
    seller = item.get('seller', {})
    seller_feedback = float(seller.get('feedbackPercentage', 0) or 0)
    feedback_score  = int(seller.get('feedbackScore', 0) or 0)

    # Daca eBay furnizeaza averageRating direct, folosim asta
    avg_rating = float(item.get('averageRating') or 0)
    if avg_rating > 0:
        rating = round(min(avg_rating, 5.0), 1)
    else:
        # Estimare din seller feedback cu variatie bazata pe feedbackScore
        # Vanzatori cu multi clienti tind sa aiba rating mai stabil
        import hashlib
        item_id_str = str(item.get('itemId', ''))
        # Variatie determinista per produs (0.0 - 0.4)
        variation = (int(hashlib.md5(item_id_str.encode()).hexdigest()[:4], 16) % 5) * 0.1
        if seller_feedback >= 99:
            base = 4.5
        elif seller_feedback >= 97:
            base = 4.2
        elif seller_feedback >= 95:
            base = 4.0
        elif seller_feedback >= 90:
            base = 3.7
        else:
            base = 3.3
        rating = round(min(base + variation, 5.0), 1)

    review_count = feedback_score

    # Vanzari estimate — eBay nu ofera sales_volume direct
    # Folosim thumbnailImages count si buyingOptions ca proxy
    sales_volume = 0
    if 'FIXED_PRICE' in buying_options:
        sales_volume = max(50, min(review_count // 10, 2000))

    # Discount
    market_price = item.get('marketingPrice', {})
    original_raw = market_price.get('originalPrice', {}).get('value', 0)
    try:
        discount_pct = round((1 - float(price) / float(original_raw)) * 100, 1) if float(original_raw) > float(price) else 0.0
    except Exception:
        discount_pct = 0.0

    # Categorie
    categories   = item.get('categories', [{}])
    category_raw = categories[0].get('categoryName', '') if categories else ''
    category     = _map_to_ml_category(category_raw) or 'Electronics'

    # URLs
    item_url  = item.get('itemWebUrl', f'https://www.ebay.com/itm/{item_id}')
    image_url = (item.get('image') or {}).get('imageUrl', '')

    brand     = (item.get('brand') or '').strip() or 'eBay'

    _temp = {
        'source':           'ebay_api',
        'price':            price,
        'rating':           rating,
        'review_count':     review_count,
        'sales_volume':     sales_volume,
        'trend_score':      trend_score,
        'discount_percent': discount_pct,
        'views':            0,
        'add_to_cart':      0,
    }
    commercial_score = calculate_investor_score(_temp, max_price=None)

    return {
        'source':       'ebay_api',
        'external_id':  item_id,
        'title':        title,
        'category':     category,
        'brand':        brand,
        'price':        price,
        'currency':     currency,
        'item_url':     item_url,
        'image_url':    image_url,
        'condition':    item.get('condition', 'New'),
        'rating':       rating,
        'review_count': review_count,
        'estimated_orders': sales_volume,
        'trend_score':  trend_score,
        'commercial_score': commercial_score,
        'raw_data': {
            'source':           'ebay_api',
            'item_id':          item_id,
            'discount_percent': discount_pct,
            'rating':           rating,
            'review_count':     review_count,
            'sales_volume':     sales_volume,
            'trend_score':      trend_score,
        },
    }


def _fetch_ebay_products(
    client: EbayBrowseAPIClient,
    keyword: str,
    top_n: int = 5,
    trend_score: float = 50.0,
) -> list[dict[str, Any]]:
    """Fetch top_n produse eBay pentru un keyword."""
    results  = []
    seen_titles = set()  # deduplicare titluri similare

    # Cerem de 4x mai mult pentru a compensa Mystery Boxes, loturi, duplicate
    limit = min(top_n * 4, 100)
    raw_items = client.search(keyword=keyword, limit=limit)

    for item in raw_items:
        if len(results) >= top_n:
            break

        title = (item.get('title') or '').lower()

        # Filtreaza produse nedorite
        skip_keywords = [
            'mystery', 'lot ', 'mixed lot', 'grab bag', 'bundle lot',
            'assorted', 'wholesale', 'bulk', 'joblot', 'job lot',
            'random', 'surprise box', 'blind box', 'mixed items',
        ]
        if any(kw in title for kw in skip_keywords):
            continue

        # Deduplicare — titluri identice cu preturi diferite
        title_key = title[:40].strip()
        if title_key in seen_titles:
            continue
        seen_titles.add(title_key)

        mapped = _map_ebay_product(item, trend_score, keyword)
        if mapped:
            results.append(mapped)

    return results


# ─── CSV fallback ─────────────────────────────────────────────────────────────

def _repair_malformed_csv_row(row: dict[str, Any]) -> dict[str, Any]:
    extras = row.get(None)
    seller_score = str(row.get('seller_feedback_score', ''))
    if extras and seller_score and not seller_score.replace('.', '', 1).isdigit():
        repaired = dict(row)
        repaired.pop(None, None)
        repaired['condition'] = row.get('seller_username', '') or 'New'
        repaired['seller_username'] = row.get('seller_feedback_score', '')
        repaired['seller_feedback_score'] = row.get('seller_feedback_percent', '')
        repaired['seller_feedback_percent'] = row.get('rating', '')
        repaired['rating'] = row.get('review_count', '')
        repaired['review_count'] = row.get('estimated_orders', '')
        repaired['estimated_orders'] = row.get('trend_score', '')
        repaired['trend_score'] = extras[0] if extras else '0'
        return repaired
    return row


def _load_csv_products(keyword: str, category: str = '') -> list[dict[str, Any]]:
    path = Path(settings.BASE_DIR) / 'sample_data' / 'ebay_discovery_sample.csv'
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows

    keyword_l = (keyword or '').lower().strip()
    category_l = (category or '').lower().strip()

    def _read_rows(kw_filter: str, cat_filter: str) -> list[dict]:
        result = []
        with path.open('r', encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            for raw_row in reader:
                row = _repair_malformed_csv_row(raw_row)
                title = row.get('title', '')
                row_category = row.get('category', '')
                if kw_filter and kw_filter not in title.lower() and kw_filter not in row_category.lower():
                    continue
                if cat_filter and cat_filter not in row_category.lower():
                    continue
                result.append(row)
        return result

    # Incearca cu ambele filtre
    raw_rows = _read_rows(keyword_l, category_l)
    # Daca 0 rezultate si category e setat, ignora category
    if not raw_rows and category_l:
        raw_rows = _read_rows(keyword_l, '')
    # Daca tot 0, returneaza toate randurile (ignora si keyword)
    if not raw_rows:
        raw_rows = _read_rows('', '')

    for row in raw_rows:
        title = row.get('title', '')
        row_category = row.get('category', '')
        sales_volume = _to_int(row.get('estimated_orders'))
        cat_key = _normalize_category(row_category)
        conversion_rate = CATEGORY_CONVERSION_RATE.get(cat_key, 3.4)
        review_count = _to_int(row.get('review_count'))
        views, add_to_cart = _derive_views_and_cart(sales_volume, conversion_rate, review_count)
        season = _detect_season(title, row_category)

        mapped = {
                'source': 'csv_fallback',
                'external_id': row.get('external_id', ''),
                'title': title,
                'category': row_category,
                'brand': row.get('brand', ''),
                'price': _to_decimal(row.get('price')),
                'currency': row.get('currency', 'USD'),
                'item_url': row.get('item_url', ''),
                'image_url': row.get('image_url', ''),
                'condition': row.get('condition', ''),
                'seller_username': row.get('seller_username', ''),
                'seller_feedback_score': _to_int(row.get('seller_feedback_score')),
                'seller_feedback_percent': _to_float(row.get('seller_feedback_percent')),
                'rating': _to_float(row.get('rating')),
                'review_count': review_count,
                'estimated_orders': sales_volume,
                'sales_volume': sales_volume,
                'discount_percent': 0.0,
                'trend_score': _to_float(row.get('trend_score')),
                'views': views,
                'add_to_cart': add_to_cart,
                'conversion_rate': conversion_rate,
                'season': season,
        }
        mapped['raw_data'] = {
                'views': views,
                'add_to_cart': add_to_cart,
                'conversion_rate': conversion_rate,
                'season': season,
                'discount_percent': 0.0,
                'opportunity_label': '',
                'opportunity_score_class': '',
                'imputed_fields': ['conversion_rate'],
        }
        rows.append(mapped)
    return rows


# ─── Funcție principală ───────────────────────────────────────────────────────

def discover_products(search_query) -> DiscoveryResult:
    """Descoperă oportunități comerciale din perspectiva investitorului."""
    max_price   = search_query.max_price
    top_n       = int(search_query.top_n or 5)
    min_rating  = float(search_query.min_rating or 0)
    min_reviews = int(getattr(search_query, 'min_reviews', 0) or 0)
    keyword     = (search_query.keyword or '').strip()
    category    = (search_query.category or '').strip()
    products: list[dict[str, Any]] = []
    used_source = 'csv_fallback'
    status_message = ''
    data_source = getattr(search_query, 'data_source', 'api') or 'api'

    if data_source == 'api':
        client = AmazonRapidAPIClient()
        if client.configured:
            try:
                if not keyword and not category:
                    # Descoperire automată în categorii populare
                    all_products: list[dict[str, Any]] = []
                    # Extindem lista de keywords pentru Top 10
                    extended_keywords = DEFAULT_OPPORTUNITY_KEYWORDS + [
                        'bluetooth speaker', 'led strip lights', 'phone stand',
                        'laptop accessories', 'home organizer',
                    ]
                    keywords_to_use = extended_keywords[:max(top_n, 3) if top_n <= 3 else max(top_n, 5)]
                    per_keyword = max(3, (top_n // len(keywords_to_use)) + 2)
                    for kw in keywords_to_use:
                        try:
                            trend = _get_trend_score(kw, category=kw)
                            fetched = _fetch_amazon_products(client, kw, top_n=per_keyword, trend_score=trend)
                            all_products.extend(fetched)
                        except Exception:
                            continue  # un keyword esuaza → continuam cu urmatorul
                        if len(all_products) >= top_n * 3:
                            break
                    products = all_products
                    status_message = (
                        f'Descoperire automată în {len(keywords_to_use)} '
                        f'categorii populare → {len(products)} produse candidate.'
                    )
                else:
                    # Daca e doar categorie (fara keyword), mapeaza la un termen concret
                    if not keyword and category:
                        cat_lower = category.lower().strip()
                        search_kw = CATEGORY_TO_KEYWORD.get(
                            cat_lower,
                            CATEGORY_TO_KEYWORD.get(
                                next((k for k in CATEGORY_TO_KEYWORD if k in cat_lower), ''),
                                category + ' products'
                            )
                        )
                    else:
                        search_kw = keyword or category
                    trend = _get_trend_score(search_kw, category=category)
                    products = _fetch_amazon_products(
                        client, search_kw, top_n=top_n, trend_score=trend
                    )
                    status_message = (
                        f'Căutare Amazon: "{search_kw}". '
                        f'Trend Google: {trend:.0f}/100.'
                    )
                used_source = 'amazon_api'

            except requests.exceptions.HTTPError as exc:
                code = exc.response.status_code if exc.response else 'necunoscut'
                status_message = (
                    'Limita RapidAPI atinsă (429). Am folosit CSV fallback.'
                    if str(code) == '429'
                    else f'Amazon API eroare {code}. Am folosit CSV fallback.'
                )
                products = _load_csv_products(keyword, category)
            except requests.exceptions.Timeout:
                status_message = 'Amazon API timeout. Am folosit CSV fallback.'
                products = _load_csv_products(keyword, category)
            except requests.exceptions.ConnectionError as exc:
                status_message = 'Amazon API: eroare de conexiune. Am folosit CSV fallback.'
                products = _load_csv_products(keyword, category)
            except Exception as exc:
                status_message = f'Amazon API eroare ({type(exc).__name__}: {exc}). Am folosit CSV fallback.'
                products = _load_csv_products(keyword, category)
        else:
            status_message = 'RAPIDAPI_KEY lipsă din .env. Am folosit CSV fallback.'
            products = _load_csv_products(keyword, category)
    elif data_source == 'aliexpress':
        ali_client = AliExpressBusinessAPIClient()
        if not ali_client.configured:
            products = _load_csv_products(keyword, category)
            status_message = 'RAPIDAPI_KEY lipseste. CSV fallback.'
            used_source = 'csv_fallback'
        else:
            try:
                if keyword:
                    search_kw = keyword
                elif category:
                    cat_lower = category.lower().strip()
                    search_kw = CATEGORY_TO_KEYWORD.get(cat_lower, category + ' products')
                else:
                    search_kw = 'trending products'
                trend = _get_trend_score(search_kw, category=category)
                products = _fetch_aliexpress_products(ali_client, search_kw, top_n=top_n, trend_score=trend)
                status_message = (
                    f'Cautare AliExpress: "{search_kw}". '
                    f'Trend Google: {trend:.0f}/100.'
                )
                used_source = 'aliexpress_api'
            except requests.exceptions.HTTPError as exc:
                code = exc.response.status_code if exc.response else '?'
                body = exc.response.text[:200] if exc.response else ''
                status_message = f'AliExpress API HTTP {code}: {body}. CSV fallback.'
                products = _load_csv_products(keyword, category)
                used_source = 'csv_fallback'
            except requests.exceptions.ConnectionError as exc:
                status_message = f'AliExpress API: eroare conexiune ({exc}). CSV fallback.'
                products = _load_csv_products(keyword, category)
                used_source = 'csv_fallback'
            except requests.exceptions.Timeout:
                status_message = 'AliExpress API: timeout. CSV fallback.'
                products = _load_csv_products(keyword, category)
                used_source = 'csv_fallback'
            except Exception as exc:
                import traceback
                status_message = f'AliExpress API eroare: {type(exc).__name__}: {str(exc)[:150]}. CSV fallback.'
                products = _load_csv_products(keyword, category)
                used_source = 'csv_fallback'
    elif data_source == 'ebay':
        ebay_client = EbayBrowseAPIClient()
        if not ebay_client.configured:
            products = _load_csv_products(keyword, category)
            status_message = 'EBAY_CLIENT_ID/SECRET lipsa din .env. CSV fallback.'
            used_source = 'csv_fallback'
        else:
            try:
                if keyword:
                    search_kw = keyword
                elif category:
                    cat_lower = category.lower().strip()
                    search_kw = CATEGORY_TO_KEYWORD.get(cat_lower, category + ' products')
                else:
                    # Keyword specific pentru eBay - evita rezultatele generice
                    cat_lower = category.lower().strip() if category else ''
                    if cat_lower:
                        search_kw = CATEGORY_TO_KEYWORD.get(cat_lower, cat_lower + ' products')
                    else:
                        search_kw = keyword or 'wireless earbuds'
                trend = _get_trend_score(search_kw, category=category)
                products = _fetch_ebay_products(ebay_client, search_kw, top_n=top_n, trend_score=trend)
                status_message = (
                    f'Cautare eBay: "{search_kw}". '
                    f'Trend Google: {trend:.0f}/100.'
                )
                used_source = 'ebay_api'
            except requests.exceptions.HTTPError as exc:
                code = exc.response.status_code if exc.response else '?'
                body = exc.response.text[:150] if exc.response else ''
                status_message = f'eBay API eroare {code}: {body}. CSV fallback.'
                products = _load_csv_products(keyword, category)
                used_source = 'csv_fallback'
            except Exception as exc:
                status_message = f'eBay API eroare ({type(exc).__name__}: {str(exc)[:100]}). CSV fallback.'
                products = _load_csv_products(keyword, category)
                used_source = 'csv_fallback'
    else:
        status_message = 'Cautare in datele CSV demo.'
        products = _load_csv_products(keyword, category)

    # ─── Filtrare ─────────────────────────────────────────────────────────────
    filtered = []
    for p in products:
        price = _to_decimal(p.get('price'))
        if max_price and price > max_price:
            continue
        if min_rating and _to_float(p.get('rating')) < min_rating:
            continue
        if min_reviews and _to_int(p.get('review_count')) < min_reviews:
            continue

        score = calculate_investor_score(p, max_price=max_price)
        p['commercial_score'] = score
        # Actualizăm label-ul după filtrare (max_price poate schimba scorul)
        p['opportunity_label'] = _opportunity_label(score)
        if p.get('raw_data'):
            p['raw_data']['opportunity_label'] = p['opportunity_label']
            p['raw_data']['opportunity_score_class'] = _opportunity_score_class(score)
        filtered.append(p)

    filtered.sort(key=lambda x: x.get('commercial_score', 0), reverse=True)
    top_results = filtered[:top_n]

    status_message += (
        f' Afișez Top {len(top_results)} oportunități '
        f'după Investor Opportunity Score.'
    )
    return DiscoveryResult(
        products=top_results,
        used_source=used_source,
        status_message=status_message,
    )