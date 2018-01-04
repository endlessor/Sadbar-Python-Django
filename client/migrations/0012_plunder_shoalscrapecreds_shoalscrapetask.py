# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('djcelery', '0001_initial'),
        ('client', '0011_auto_20160907_1629'),
    ]

    operations = [
        migrations.CreateModel(
            name='Plunder',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('path', models.CharField(max_length=255, null=True, blank=True)),
                ('file_id', models.CharField(max_length=255, null=True, blank=True)),
                ('filename', models.CharField(max_length=255, null=True, blank=True)),
                ('mimetype', models.CharField(max_length=255, null=True, blank=True)),
                ('last_modified', models.DateTimeField(null=True, blank=True)),
                ('data', models.TextField(null=True)),
                ('oauth_result', models.ForeignKey(related_name='plunder', blank=True, to='client.OAuthResult', null=True)),
            ],
        ),
        migrations.CreateModel(
            name='ShoalScrapeCreds',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(default=b'', max_length=255, null=True)),
                ('username', models.CharField(max_length=255, null=True)),
                ('password', models.CharField(max_length=255, null=True)),
                ('scraper_user_agent', models.ForeignKey(related_name='shoalscrape_creds', on_delete=django.db.models.deletion.SET_NULL, blank=True, to='client.ScraperUserAgent', null=True)),
            ],
        ),
        migrations.CreateModel(
            name='ShoalScrapeTask',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('state', models.SmallIntegerField(default=0, editable=False, choices=[(0, b'Not Started'), (1, b'In Progress'), (2, b'Paused'), (3, b'Error'), (4, b'Complete')])),
                ('company', models.CharField(max_length=255, null=True)),
                ('domain', models.CharField(max_length=255, null=True)),
                ('path', models.CharField(max_length=255, null=True, blank=True)),
                ('last_started_at', models.DateTimeField(null=True, blank=True)),
                ('error', models.TextField(default=b'', null=True, blank=True)),
                ('current_task_id', models.CharField(default=b'', max_length=36, null=True, blank=True)),
                ('periodic_task', models.ForeignKey(to='djcelery.PeriodicTask', null=True)),
                ('shoalscrape_creds', models.ForeignKey(related_name='shoalscrape_tasks', to='client.ShoalScrapeCreds', null=True)),
            ],
        ),
    ]
