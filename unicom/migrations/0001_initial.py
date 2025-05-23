# Generated by Django 4.2.20 on 2025-05-20 11:04

from django.conf import settings
import django.contrib.postgres.fields
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Account',
            fields=[
                ('id', models.CharField(max_length=500, primary_key=True, serialize=False)),
                ('platform', models.CharField(choices=[('Telegram', 'Telegram'), ('WhatsApp', 'WhatsApp'), ('Internal', 'Internal'), ('Email', 'Email')], max_length=100)),
                ('is_bot', models.BooleanField(default=False)),
                ('name', models.CharField(blank=True, max_length=100, null=True)),
                ('raw', models.JSONField()),
            ],
        ),
        migrations.CreateModel(
            name='Bot',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100)),
                ('platform', models.CharField(choices=[('Telegram', 'Telegram'), ('WhatsApp', 'WhatsApp'), ('Internal', 'Internal'), ('Email', 'Email')], max_length=100)),
                ('config', models.JSONField()),
                ('active', models.BooleanField(default=False, editable=False)),
                ('confirmed_webhook_url', models.CharField(blank=True, editable=False, max_length=500, null=True)),
                ('error', models.CharField(blank=True, editable=False, max_length=500, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Chat',
            fields=[
                ('id', models.CharField(max_length=500, primary_key=True, serialize=False)),
                ('platform', models.CharField(choices=[('Telegram', 'Telegram'), ('WhatsApp', 'WhatsApp'), ('Internal', 'Internal'), ('Email', 'Email')], max_length=100)),
                ('is_private', models.BooleanField(default=True)),
                ('name', models.CharField(blank=True, max_length=100, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Message',
            fields=[
                ('id', models.CharField(max_length=500, primary_key=True, serialize=False)),
                ('platform', models.CharField(choices=[('Telegram', 'Telegram'), ('WhatsApp', 'WhatsApp'), ('Internal', 'Internal'), ('Email', 'Email')], max_length=100)),
                ('is_bot', models.BooleanField(default=False)),
                ('sender_name', models.CharField(max_length=100)),
                ('subject', models.CharField(blank=True, help_text='Subject of the message (only for email messages)', max_length=512, null=True)),
                ('text', models.TextField()),
                ('html', models.TextField(blank=True, help_text='Full HTML body (only for email messages)', null=True)),
                ('to', django.contrib.postgres.fields.ArrayField(base_field=models.EmailField(max_length=254, validators=[django.core.validators.EmailValidator()]), blank=True, default=list, help_text='List of To: addresses', size=None)),
                ('cc', django.contrib.postgres.fields.ArrayField(base_field=models.EmailField(max_length=254, validators=[django.core.validators.EmailValidator()]), blank=True, default=list, help_text='List of Cc: addresses', size=None)),
                ('bcc', django.contrib.postgres.fields.ArrayField(base_field=models.EmailField(max_length=254, validators=[django.core.validators.EmailValidator()]), blank=True, default=list, help_text='List of Bcc: addresses', size=None)),
                ('media', models.FileField(blank=True, null=True, upload_to='media/')),
                ('timestamp', models.DateTimeField()),
                ('time_sent', models.DateTimeField(blank=True, null=True)),
                ('time_delivered', models.DateTimeField(blank=True, null=True)),
                ('time_seen', models.DateTimeField(blank=True, null=True)),
                ('sent', models.BooleanField(default=False)),
                ('delivered', models.BooleanField(default=False)),
                ('seen', models.BooleanField(default=False)),
                ('raw', models.JSONField()),
                ('media_type', models.CharField(choices=[('text', 'Text'), ('html', 'HTML'), ('image', 'Image'), ('audio', 'Audio')], default='text', max_length=10)),
                ('chat', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='unicom.chat')),
                ('reply_to_message', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='replies', to='unicom.message')),
                ('sender', models.ForeignKey(on_delete=django.db.models.deletion.RESTRICT, to='unicom.account')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.RESTRICT, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-timestamp'],
            },
        ),
        migrations.CreateModel(
            name='Update',
            fields=[
                ('platform', models.CharField(choices=[('Telegram', 'Telegram'), ('WhatsApp', 'WhatsApp'), ('Internal', 'Internal'), ('Email', 'Email')], max_length=100)),
                ('id', models.CharField(max_length=100, primary_key=True, serialize=False)),
                ('payload', models.JSONField()),
                ('bot', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='unicom.bot')),
                ('message', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='unicom.message')),
            ],
        ),
        migrations.CreateModel(
            name='AccountChat',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='unicom.account')),
                ('chat', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='unicom.chat')),
            ],
            options={
                'unique_together': {('account', 'chat')},
            },
        ),
    ]
