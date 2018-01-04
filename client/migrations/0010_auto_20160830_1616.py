# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import oauth2client.contrib.django_util.models


class Migration(migrations.Migration):

    dependencies = [
        ('client', '0009_remove_landingpage_date_created'),
    ]

    operations = [
        migrations.CreateModel(
            name='OAuthConsumer',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=256, null=True)),
                ('description', models.TextField(null=True, blank=True)),
                ('client_id', models.CharField(max_length=256)),
                ('client_secret', models.CharField(max_length=256)),
                ('scope', models.CharField(max_length=256)),
                ('callback_url', models.CharField(max_length=256)),
                ('bounce_url', models.CharField(max_length=256)),
            ],
        ),
        migrations.CreateModel(
            name='OAuthEngagement',
            fields=[
                ('engagement_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='client.Engagement')),
                ('oauth_consumer', models.ForeignKey(related_name='oauth_engagements', to='client.OAuthConsumer', null=True)),
            ],
            bases=('client.engagement',),
        ),
        migrations.CreateModel(
            name='OAuthResult',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('timestamp', models.DateTimeField(null=True)),
                ('userAgent', models.CharField(max_length=255, null=True)),
                ('ip', models.GenericIPAddressField(null=True)),
                ('credentials', oauth2client.contrib.django_util.models.CredentialsField(null=True)),
                ('consumer', models.ForeignKey(related_name='oauth_results', blank=True, to='client.OAuthConsumer', null=True)),
                ('target', models.ForeignKey(related_name='oauth_results', blank=True, to='client.Target', null=True)),
            ],
        ),
        migrations.AddField(
            model_name='landingpage',
            name='date_created',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
    ]
