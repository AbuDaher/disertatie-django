# Generated manually for dissertation MVP
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('products', '0001_initial'),
        ('predictions', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='InvestmentAnalysis',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('acquisition_cost', models.DecimalField(decimal_places=2, help_text='Cost achiziție / furnizor per produs', max_digits=10)),
                ('shipping_cost', models.DecimalField(decimal_places=2, default=0, help_text='Transport / logistică per produs', max_digits=10)),
                ('marketing_cost', models.DecimalField(decimal_places=2, default=0, help_text='Cost promovare per produs', max_digits=10)),
                ('other_costs', models.DecimalField(decimal_places=2, default=0, help_text='Alte costuri per produs', max_digits=10)),
                ('platform_commission_percent', models.FloatField(default=0, help_text='Comision platformă / marketplace (%)')),
                ('recommended_selling_price', models.DecimalField(decimal_places=2, help_text='Preț de vânzare propus', max_digits=10)),
                ('estimated_units', models.PositiveIntegerField(default=1, help_text='Număr estimat de unități vândute')),
                ('commission_value', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('total_unit_cost', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('profit_per_unit', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('total_revenue', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('total_profit', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('profit_margin_percent', models.FloatField(default=0)),
                ('roi_percent', models.FloatField(default=0)),
                ('decision_label', models.CharField(choices=[('recommended', 'Merită investiția'), ('medium_risk', 'Merită cu risc mediu'), ('not_recommended', 'Nu este recomandată investiția')], default='medium_risk', max_length=40)),
                ('decision_reason', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('prediction_run', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='investment_analyses', to='predictions.predictionrun')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='investment_analyses', to='products.product')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
