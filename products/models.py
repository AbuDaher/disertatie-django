from django.db import models


class Product(models.Model):
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=120)
    brand = models.CharField(max_length=120, blank=True)
    current_price = models.DecimalField(max_digits=10, decimal_places=2)
    cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    discount_percent = models.FloatField(default=0)
    rating = models.FloatField(default=0)
    review_count = models.PositiveIntegerField(default=0)
    views = models.PositiveIntegerField(default=0)
    add_to_cart = models.PositiveIntegerField(default=0)
    sales_volume = models.PositiveIntegerField(default=0)
    stock_level = models.PositiveIntegerField(default=0)
    conversion_rate = models.FloatField(default=0)
    margin_percent = models.FloatField(default=0)
    season = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name
