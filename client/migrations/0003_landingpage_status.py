# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('client', '0002_auto_20160209_2000'),
    ]

    operations = [
        migrations.AddField(
            model_name='landingpage',
            name='status',
            field=models.SmallIntegerField(default=2, null=True, choices=[(1, b'ok'), (2, b'refresh refresh-animate'), (3, b'remove')]),
        ),
    ]
