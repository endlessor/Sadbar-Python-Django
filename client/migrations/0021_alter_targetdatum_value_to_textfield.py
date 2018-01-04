# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('client', '0020_resultevent_vector_email_related_name'),
    ]

    operations = [
        migrations.AlterField(
            model_name='targetdatum',
            name='value',
            field=models.TextField(null=True, blank=True),
        ),
    ]
