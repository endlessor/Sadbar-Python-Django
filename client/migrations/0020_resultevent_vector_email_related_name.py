# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('client', '0019_remove_campaign_url'),
    ]

    operations = [
        migrations.AlterField(
            model_name='vectoremail',
            name='result_event',
            field=models.ManyToManyField(related_name='vector_email', to='client.ResultEvent'),
        ),
    ]
