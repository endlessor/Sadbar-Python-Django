# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('client', '0023_merge'),
    ]

    operations = [
        migrations.AddField(
            model_name='phishingdomain',
            name='protocol',
            field=models.CharField(max_length=5, null=True, choices=[(b'http', b'http'), (b'https', b'https')]),
        ),
    ]
