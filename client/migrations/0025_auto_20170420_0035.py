# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('client', '0024_phishingdomain_protocol'),
    ]

    operations = [
        migrations.AddField(
            model_name='emailtemplate',
            name='description',
            field=models.TextField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='landingpage',
            name='description',
            field=models.TextField(null=True, blank=True),
        ),
    ]
