# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('client', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='landingpage',
            name='is_page',
        ),
        migrations.AddField(
            model_name='landingpage',
            name='page_type',
            field=models.CharField(default=b'page', max_length=10, choices=[(b'url', b'URL'), (b'page', b'Saved Page'), (b'manual', b'Manual')]),
        ),
        migrations.AlterField(
            model_name='landingpage',
            name='url',
            field=models.CharField(max_length=255, null=True, blank=True),
        ),
    ]
