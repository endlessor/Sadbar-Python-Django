# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('client', '0007_auto_20160810_0105'),
    ]

    operations = [
        migrations.AddField(
            model_name='landingpage',
            name='date_created',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
    ]
