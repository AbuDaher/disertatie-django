from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('analytics', '0001_initial'),
        ('investment', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='investmentanalysis',
            name='analysis_run',
            field=models.ForeignKey(blank=True, help_text='Verificarea / sesiunea de analiză din care face parte analiza investițională.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='investment_analyses', to='analytics.analysisrun'),
        ),
    ]
