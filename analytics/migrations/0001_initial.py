# Generated manually for Business AI decision platform
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='AnalysisRun',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('source_type', models.CharField(choices=[('manual', 'Evaluare manuală'), ('csv_upload', 'Încărcare CSV'), ('discovery', 'Căutare oportunități'), ('ebay_api', 'eBay API'), ('csv_fallback', 'CSV fallback')], default='manual', max_length=40)),
                ('keyword', models.CharField(blank=True, max_length=200)),
                ('source_file_name', models.CharField(blank=True, max_length=255)),
                ('products_count', models.PositiveIntegerField(default=0)),
                ('predictions_count', models.PositiveIntegerField(default=0)),
                ('investment_count', models.PositiveIntegerField(default=0)),
                ('status', models.CharField(choices=[('created', 'Creată'), ('completed', 'Finalizată'), ('error', 'Eroare')], default='created', max_length=30)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Verificare analiză',
                'verbose_name_plural': 'Verificări analiză',
                'ordering': ['-created_at'],
            },
        ),
    ]
