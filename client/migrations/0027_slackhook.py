# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('client', '0026_landing_page_url_max_len_1000'),
    ]

    operations = [
        migrations.CreateModel(
            name='SlackHook',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('webhook_url', models.TextField(default=b'', blank=True)),
                ('description', models.TextField(default=b'', blank=True)),
            ],
        ),
    ]
