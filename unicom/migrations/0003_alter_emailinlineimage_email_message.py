# Generated by Django 4.2.20 on 2025-06-07 03:50

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('unicom', '0002_emailinlineimage'),
    ]

    operations = [
        migrations.AlterField(
            model_name='emailinlineimage',
            name='email_message',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='inline_images', to='unicom.message'),
        ),
    ]
