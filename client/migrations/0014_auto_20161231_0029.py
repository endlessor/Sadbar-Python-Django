# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('client', '0013_shoalscrapetask_company_linkedin_id'),
    ]

    operations = [
        migrations.CreateModel(
            name='OpenRedirect',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('url', models.CharField(max_length=500, null=True)),
            ],
        ),
        migrations.AlterField(
            model_name='engagement',
            name='path',
            field=models.CharField(default=b'', max_length=500, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='phishingdomain',
            name='domain_name',
            field=models.CharField(max_length=500, null=True),
        ),
        migrations.AddField(
            model_name='engagement',
            name='open_redirect',
            field=models.ForeignKey(related_name='engagement', on_delete=django.db.models.deletion.SET_NULL, blank=True, to='client.OpenRedirect', null=True),
        ),
    ]
