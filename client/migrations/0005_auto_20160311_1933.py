# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('client', '0004_auto_20160219_2005'),
    ]

    operations = [
        migrations.AlterField(
            model_name='scheduleinterval',
            name='interval',
            field=models.ForeignKey(to='djcelery.IntervalSchedule', null=True),
        ),
    ]
