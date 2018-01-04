# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('client', '0017_auto_20161118_1923'),
    ]

    operations = [
        migrations.AlterField(
            model_name='shoalscrapetask',
            name='periodic_task',
            field=models.ForeignKey(blank=True, to='djcelery.PeriodicTask', null=True),
        ),
    ]
