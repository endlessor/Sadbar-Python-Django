# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('client', '0008_landingpage_date_created'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='landingpage',
            name='date_created',
        ),
    ]
