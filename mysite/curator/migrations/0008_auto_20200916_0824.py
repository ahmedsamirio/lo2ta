# Generated by Django 3.0.8 on 2020-09-16 08:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('curator', '0007_auto_20200916_0819'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ad',
            name='imgs',
            field=models.CharField(blank=True, max_length=2000, null=True),
        ),
    ]
