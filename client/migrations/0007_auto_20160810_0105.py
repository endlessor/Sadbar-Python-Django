# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('client', '0006_auto_20160630_0534'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailServer',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('host', models.CharField(max_length=100, null=True)),
                ('port', models.IntegerField(null=True)),
                ('use_tls', models.BooleanField(default=False)),
                ('login', models.CharField(max_length=100, null=True)),
                ('password', models.CharField(max_length=100, null=True)),
                ('test_recipient', models.EmailField(default=b'info@rhinosecuritylabs.com', max_length=254, null=True, blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='PhishingDomain',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('domain_name', models.CharField(max_length=100, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='ScraperUserAgent',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=100, null=True)),
                ('user_agent_data', models.CharField(default=b'', max_length=512, null=True)),
            ],
        ),
        migrations.RemoveField(
            model_name='emailtemplate',
            name='email_config',
        ),
        migrations.RemoveField(
            model_name='emailtemplate',
            name='re_header',
        ),
        migrations.RemoveField(
            model_name='engagement',
            name='url',
        ),
        migrations.AddField(
            model_name='engagement',
            name='path',
            field=models.CharField(default=b'', max_length=100, null=True, blank=True),
        ),
        migrations.DeleteModel(
            name='EmailConfig',
        ),
        migrations.AddField(
            model_name='engagement',
            name='domain',
            field=models.ForeignKey(related_name='engagement', on_delete=django.db.models.deletion.SET_NULL, to='client.PhishingDomain', null=True),
        ),
        migrations.AddField(
            model_name='engagement',
            name='email_server',
            field=models.ForeignKey(related_name='engagement', on_delete=django.db.models.deletion.SET_NULL, to='client.EmailServer', null=True),
        ),
        migrations.AddField(
            model_name='landingpage',
            name='scraper_user_agent',
            field=models.ForeignKey(related_name='landing_pages', on_delete=django.db.models.deletion.SET_NULL, blank=True, to='client.ScraperUserAgent', null=True),
        ),
    ]
