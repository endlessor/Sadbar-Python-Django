# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('client', '0014_profile'),
    ]

    operations = [
        migrations.RenameField(
            model_name='targetdatum',
            old_name='datumLabel',
            new_name='label',
        ),
        migrations.RenameField(
            model_name='targetdatum',
            old_name='datumValue',
            new_name='value',
        ),
        migrations.RemoveField(
            model_name='targetdatum',
            name='shortCode',
        ),
        migrations.AddField(
            model_name='targetdatum',
            name='target_list',
            field=models.ForeignKey(to='client.TargetList', null=True),
        ),
    ]
