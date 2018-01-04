# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('client', '0010_auto_20160830_1616'),
    ]

    operations = [
        migrations.AddField(
            model_name='oauthresult',
            name='email',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='oauthresult',
            name='oauth_engagement',
            field=models.ForeignKey(related_name='oauth_results', on_delete=django.db.models.deletion.SET_NULL, blank=True, to='client.OAuthEngagement', null=True),
        ),
        migrations.AlterField(
            model_name='oauthresult',
            name='target',
            field=models.ForeignKey(related_name='oauth_results', on_delete=django.db.models.deletion.SET_NULL, blank=True, to='client.Target', null=True),
        ),
    ]
