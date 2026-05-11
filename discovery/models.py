from django.db import models


class SearchQuery(models.Model):
    SOURCE_API = 'api'
    SOURCE_CSV = 'csv'
    SOURCE_CHOICES = [
        (SOURCE_API, 'eBay API'),
        (SOURCE_CSV, 'CSV fallback'),
    ]

    keyword = models.CharField(max_length=200)
    category = models.CharField(max_length=120, blank=True)
    max_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    min_rating = models.FloatField(default=0)
    min_reviews = models.PositiveIntegerField(default=0)
    top_n = models.PositiveIntegerField(default=5)
    data_source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_CSV)
    used_source = models.CharField(max_length=40, blank=True)
    status_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.keyword} - Top {self.top_n}'


class DiscoveredProduct(models.Model):
    search_query = models.ForeignKey(SearchQuery, on_delete=models.CASCADE, related_name='products')
    linked_product = models.ForeignKey('products.Product', on_delete=models.SET_NULL, null=True, blank=True)

    source = models.CharField(max_length=40, default='csv')
    external_id = models.CharField(max_length=160, blank=True)
    title = models.CharField(max_length=300)
    category = models.CharField(max_length=120, blank=True)
    brand = models.CharField(max_length=120, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='USD')
    item_url = models.URLField(blank=True)
    image_url = models.URLField(blank=True)
    condition = models.CharField(max_length=120, blank=True)

    seller_username = models.CharField(max_length=160, blank=True)
    seller_feedback_score = models.PositiveIntegerField(default=0)
    seller_feedback_percent = models.FloatField(default=0)

    rating = models.FloatField(default=0)
    review_count = models.PositiveIntegerField(default=0)
    estimated_orders = models.PositiveIntegerField(default=0)
    trend_score = models.FloatField(default=0)
    commercial_score = models.FloatField(default=0)

    raw_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-commercial_score', 'price']

    def __str__(self):
        return self.title
