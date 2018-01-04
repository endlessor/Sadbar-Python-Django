# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('client', '0016_add_migrations_to_repo_pt_2'),
    ]

    operations = [
        migrations.AlterField(
            model_name='targetdatum',
            name='value',
            field=models.CharField(max_length=500, null=True, blank=True),
        ),
    ]
