# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('client', '0018_auto_20161204_1000'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='campaign',
            name='url',
        ),
    ]
