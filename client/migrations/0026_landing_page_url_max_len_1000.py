# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('client', '0025_auto_20170420_0035'),
    ]

    operations = [
        migrations.AlterField(
            model_name='landingpage',
            name='url',
            field=models.CharField(max_length=1000, null=True, blank=True),
        ),
    ]
