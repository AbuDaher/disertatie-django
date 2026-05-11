from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import requests
from django.conf import settings


EBAY_SCOPE = 'https://api.ebay.com/oauth/api_scope'


@dataclass
class DiscoveryResult:
    products: list[dict[str, Any]]
    used_source: str
    status_message: str


def _to_decimal(value: Any, default: str = '0') -> Decimal:
    try:
        if value in (None, ''):
            return Decimal(default)
        return Decimal(str(value)).quantize(Decimal('0.01'))
    except Exception:
        return Decimal(default)


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(float(value))
    except Exception:
        return default


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ''):
            return default
        return float(value)
    except Exception:
        return default


def calculate_commercial_score(product: dict[str, Any], max_price: Decimal | None = None) -> float:
    """Scor 0-100 pentru rankingul oportunităților comerciale.

    Pentru CSV folosim rating, reviews, orders și trend. Pentru eBay API unele câmpuri
    lipsesc, deci scorul folosește preț, feedback seller și datele disponibile.
    """
    rating = _to_float(product.get('rating'))
    reviews = _to_int(product.get('review_count'))
    orders = _to_int(product.get('estimated_orders'))
    trend = _to_float(product.get('trend_score'))
    seller_feedback = _to_int(product.get('seller_feedback_score'))
    seller_percent = _to_float(product.get('seller_feedback_percent'))
    price = _to_decimal(product.get('price'))

    rating_score = min(rating / 5, 1) * 25
    review_score = min(reviews / 500, 1) * 20
    orders_score = min(orders / 1000, 1) * 25
    trend_score = min(trend / 100, 1) * 15
    seller_score = min(seller_feedback / 5000, 1) * 8 + min(seller_percent / 100, 1) * 4

    price_score = 3
    if max_price and max_price > 0:
        if price <= max_price:
            price_score = min((max_price - price) / max_price, Decimal('1')) * Decimal('3')
            price_score = float(price_score)
        else:
            price_score = -12

    score = rating_score + review_score + orders_score + trend_score + seller_score + price_score
    return round(max(0, min(score, 100)), 2)


class EbayBrowseClient:
    def __init__(self):
        self.client_id = os.getenv('EBAY_CLIENT_ID', '').strip()
        self.client_secret = os.getenv('EBAY_CLIENT_SECRET', '').strip()
        self.marketplace_id = os.getenv('EBAY_MARKETPLACE_ID', 'EBAY_US').strip()
        self.environment = os.getenv('EBAY_ENVIRONMENT', 'production').strip().lower()

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    @property
    def api_base(self) -> str:
        if self.environment == 'sandbox':
            return 'https://api.sandbox.ebay.com'
        return 'https://api.ebay.com'

    def get_application_token(self) -> str:
        url = f'{self.api_base}/identity/v1/oauth2/token'
        response = requests.post(
            url,
            auth=(self.client_id, self.client_secret),
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            data={'grant_type': 'client_credentials', 'scope': EBAY_SCOPE},
            timeout=20,
        )
        response.raise_for_status()
        return response.json()['access_token']

    def search(self, keyword: str, limit: int = 20) -> list[dict[str, Any]]:
        token = self.get_application_token()
        url = f'{self.api_base}/buy/browse/v1/item_summary/search'
        response = requests.get(
            url,
            headers={
                'Authorization': f'Bearer {token}',
                'X-EBAY-C-MARKETPLACE-ID': self.marketplace_id,
            },
            params={'q': keyword, 'limit': min(max(limit, 1), 50)},
            timeout=20,
        )
        response.raise_for_status()
        return response.json().get('itemSummaries', [])


def _map_ebay_item(item: dict[str, Any], category: str = '') -> dict[str, Any]:
    seller = item.get('seller') or {}
    price = item.get('price') or {}
    image = item.get('image') or {}
    categories = item.get('categories') or []
    category_name = category
    if not category_name and categories:
        category_name = categories[0].get('categoryName', '')

    return {
        'source': 'ebay_api',
        'external_id': item.get('itemId', ''),
        'title': item.get('title', 'Produs eBay'),
        'category': category_name or 'eBay',
        'brand': '',
        'price': _to_decimal(price.get('value')),
        'currency': price.get('currency', 'USD'),
        'item_url': item.get('itemWebUrl', ''),
        'image_url': image.get('imageUrl', ''),
        'condition': item.get('condition', ''),
        'seller_username': seller.get('username', ''),
        'seller_feedback_score': _to_int(seller.get('feedbackScore')),
        'seller_feedback_percent': _to_float(seller.get('feedbackPercentage')),
        # eBay Browse API nu returnează constant comenzi/ratinguri produs.
        # Aceste câmpuri rămân 0 și pot fi completate ulterior din alte surse.
        'rating': 0,
        'review_count': 0,
        'estimated_orders': 0,
        'trend_score': 0,
        'raw_data': item,
    }


def _repair_malformed_csv_row(row: dict[str, Any]) -> dict[str, Any]:
    """Repară rândurile CSV dacă au apărut virgule în plus la coloanele URL/imagine.

    Versiunea inițială a fișierului fallback avea trei virgule după item_url, ceea ce
    deplasa câmpurile: feedback-ul vânzătorului ajungea în rating, ratingul ajungea
    în review_count etc. Această funcție face loaderul tolerant, dar fișierul CSV
    corectat din patch trebuie folosit pentru date noi.
    """
    extras = row.get(None)
    seller_feedback_score = str(row.get('seller_feedback_score', ''))

    # Semnal clar de rând deplasat: seller_feedback_score conține numele vânzătorului.
    if extras and seller_feedback_score and not seller_feedback_score.replace('.', '', 1).isdigit():
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

    with path.open('r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        for raw_row in reader:
            row = _repair_malformed_csv_row(raw_row)
            title = row.get('title', '')
            row_category = row.get('category', '')
            if keyword_l and keyword_l not in title.lower() and keyword_l not in row_category.lower():
                continue
            if category_l and category_l not in row_category.lower():
                continue
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
                'review_count': _to_int(row.get('review_count')),
                'estimated_orders': _to_int(row.get('estimated_orders')),
                'trend_score': _to_float(row.get('trend_score')),
            }
            mapped['raw_data'] = dict(mapped)
            rows.append(mapped)
    return rows


def discover_products(search_query) -> DiscoveryResult:
    max_price = search_query.max_price
    top_n = int(search_query.top_n or 5)
    requested_source = search_query.data_source
    products: list[dict[str, Any]] = []
    used_source = 'csv_fallback'
    status_message = ''

    if requested_source == 'api':
        client = EbayBrowseClient()
        if client.configured:
            try:
                api_items = client.search(search_query.keyword, limit=max(top_n * 4, 20))
                products = [_map_ebay_item(item, search_query.category) for item in api_items]
                used_source = 'ebay_api'
                status_message = f'Am preluat {len(products)} produse din eBay Browse API.'
            except Exception as exc:
                status_message = f'eBay API indisponibil sau configurare incompletă: {exc}. Am folosit CSV fallback.'
                products = _load_csv_products(search_query.keyword, search_query.category)
        else:
            status_message = 'Cheile eBay API nu sunt configurate în .env. Am folosit CSV fallback.'
            products = _load_csv_products(search_query.keyword, search_query.category)
    else:
        status_message = 'Căutarea a folosit datele CSV fallback.'
        products = _load_csv_products(search_query.keyword, search_query.category)

    filtered = []
    for p in products:
        if max_price and _to_decimal(p.get('price')) > max_price:
            continue
        if _to_float(p.get('rating')) < float(search_query.min_rating or 0):
            # Pentru API, ratingul poate lipsi; nu eliminăm automat dacă rating minim este 0.
            continue
        if _to_int(p.get('review_count')) < int(search_query.min_reviews or 0):
            continue
        p['commercial_score'] = calculate_commercial_score(p, max_price=max_price)
        filtered.append(p)

    filtered.sort(key=lambda x: x.get('commercial_score', 0), reverse=True)
    return DiscoveryResult(products=filtered[:top_n], used_source=used_source, status_message=status_message)
