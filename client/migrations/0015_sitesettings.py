# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('client', '0014_auto_20161231_0029'),
    ]

    operations = [
        migrations.CreateModel(
            name='SiteSettings',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('_singleton', models.BooleanField(default=True, unique=True, editable=False)),
                ('public_ip', models.GenericIPAddressField(default=b'127.0.0.1', null=True, blank=True)),
            ],
        ),
    ]
