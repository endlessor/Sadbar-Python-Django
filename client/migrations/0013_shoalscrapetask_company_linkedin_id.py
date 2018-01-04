# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('client', '0012_plunder_shoalscrapecreds_shoalscrapetask'),
    ]

    operations = [
        migrations.AddField(
            model_name='shoalscrapetask',
            name='company_linkedin_id',
            field=models.CharField(max_length=255, null=True),
        ),
    ]
