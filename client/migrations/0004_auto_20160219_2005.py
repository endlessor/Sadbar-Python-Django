# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('client', '0003_landingpage_status'),
    ]

    operations = [
        migrations.AlterField(
            model_name='resultevent',
            name='event_type',
            field=models.IntegerField(default=0, choices=[(0, b'Not sent'), (1, b'Open'), (2, b'Click'), (3, b'Submit')]),
        ),
    ]
