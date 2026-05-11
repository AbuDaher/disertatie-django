from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('analytics', '0001_initial'),
        ('predictions', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='predictionrun',
            name='analysis_run',
            field=models.ForeignKey(blank=True, help_text='Verificarea / sesiunea de analiză din care face parte predicția.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='prediction_runs', to='analytics.analysisrun'),
        ),
    ]
