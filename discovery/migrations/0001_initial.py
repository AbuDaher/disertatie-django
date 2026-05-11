# Generated manually for the dissertation MVP.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('products', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='SearchQuery',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('keyword', models.CharField(max_length=200)),
                ('category', models.CharField(blank=True, max_length=120)),
                ('max_price', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('min_rating', models.FloatField(default=0)),
                ('min_reviews', models.PositiveIntegerField(default=0)),
                ('top_n', models.PositiveIntegerField(default=5)),
                ('data_source', models.CharField(choices=[('api', 'eBay API'), ('csv', 'CSV fallback')], default='csv', max_length=20)),
                ('used_source', models.CharField(blank=True, max_length=40)),
                ('status_message', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='DiscoveredProduct',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source', models.CharField(default='csv', max_length=40)),
                ('external_id', models.CharField(blank=True, max_length=160)),
                ('title', models.CharField(max_length=300)),
                ('category', models.CharField(blank=True, max_length=120)),
                ('brand', models.CharField(blank=True, max_length=120)),
                ('price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('currency', models.CharField(default='USD', max_length=10)),
                ('item_url', models.URLField(blank=True)),
                ('image_url', models.URLField(blank=True)),
                ('condition', models.CharField(blank=True, max_length=120)),
                ('seller_username', models.CharField(blank=True, max_length=160)),
                ('seller_feedback_score', models.PositiveIntegerField(default=0)),
                ('seller_feedback_percent', models.FloatField(default=0)),
                ('rating', models.FloatField(default=0)),
                ('review_count', models.PositiveIntegerField(default=0)),
                ('estimated_orders', models.PositiveIntegerField(default=0)),
                ('trend_score', models.FloatField(default=0)),
                ('commercial_score', models.FloatField(default=0)),
                ('raw_data', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('linked_product', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='products.product')),
                ('search_query', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='products', to='discovery.searchquery')),
            ],
            options={'ordering': ['-commercial_score', 'price']},
        ),
    ]
