# Generated by Django 2.0.6 on 2018-09-24 20:00

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('daas_app', '0002_remove_statistics_exception_info'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sample',
            name='statistics',
            field=models.ForeignKey(default=None, on_delete=django.db.models.deletion.CASCADE, to='daas_app.Statistics'),
        ),
    ]