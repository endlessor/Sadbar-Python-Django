# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('djcelery', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Campaign',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=100, null=True)),
                ('description', models.TextField(null=True, blank=True)),
                ('url', models.CharField(max_length=100, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Client',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=100, null=True)),
                ('url', models.CharField(max_length=100, null=True)),
                ('default_time_zone', models.CharField(max_length=50, null=True, choices=[(b'Etc/GMT+12', b'UTC-12:00'), (b'Etc/GMT+11', b'UTC-11:00'), (b'Etc/GMT+10', b'UTC-10:00'), (b'Etc/GMT+9', b'UTC-09:00'), (b'Etc/GMT+8', b'UTC-08:00'), (b'Etc/GMT+7', b'UTC-07:00'), (b'Etc/GMT+6', b'UTC-06:00'), (b'Etc/GMT+5', b'UTC-05:00'), (b'Etc/GMT+4', b'UTC-04:00'), (b'Etc/GMT+3', b'UTC-03:00'), (b'Etc/GMT+2', b'UTC-02:00'), (b'Etc/GMT+1', b'UTC-01:00'), (b'Etc/GMT+0', b'UTC+00:00'), (b'Etc/GMT-1', b'UTC+01:00'), (b'Etc/GMT-2', b'UTC+02:00'), (b'Etc/GMT-3', b'UTC+03:00'), (b'Etc/GMT-4', b'UTC+04:00'), (b'Etc/GMT-5', b'UTC+05:00'), (b'Etc/GMT-6', b'UTC+06:00'), (b'Etc/GMT-7', b'UTC+07:00'), (b'Etc/GMT-8', b'UTC+08:00'), (b'Etc/GMT-9', b'UTC+09:00'), (b'Etc/GMT-10', b'UTC+10:00'), (b'Etc/GMT-11', b'UTC+11:00'), (b'Etc/GMT-12', b'UTC+12:00'), (b'Etc/GMT-13', b'UTC+13:00'), (b'Etc/GMT-14', b'UTC+14:00')])),
            ],
        ),
        migrations.CreateModel(
            name='EmailConfig',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('host', models.CharField(max_length=100, null=True)),
                ('port', models.IntegerField(null=True)),
                ('use_tls', models.BooleanField(default=False)),
                ('login', models.CharField(max_length=100, null=True)),
                ('password', models.CharField(max_length=100, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='EmailTemplate',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=100, null=True)),
                ('re_header', models.EmailField(max_length=254, null=True)),
                ('from_header', models.CharField(max_length=100, null=True)),
                ('subject_header', models.CharField(max_length=100, null=True)),
                ('template', models.TextField(null=True)),
                ('email_config', models.OneToOneField(null=True, to='client.EmailConfig')),
            ],
        ),
        migrations.CreateModel(
            name='Engagement',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=100, null=True)),
                ('description', models.TextField(null=True, blank=True)),
                ('url', models.CharField(max_length=100, null=True)),
                ('campaign', models.ForeignKey(to='client.Campaign', null=True)),
                ('email_template', models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, to='client.EmailTemplate', null=True)),
            ],
        ),
        migrations.CreateModel(
            name='LandingPage',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=100, null=True)),
                ('url', models.CharField(max_length=255, null=True)),
                ('path', models.CharField(max_length=255, null=True, blank=True)),
                ('is_redirect_page', models.BooleanField(default=False)),
                ('is_page', models.BooleanField(default=True)),
            ],
        ),
        migrations.CreateModel(
            name='Result',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('sent_timestamp', models.DateTimeField(null=True)),
                ('engagement', models.ForeignKey(to='client.Engagement', null=True)),
            ],
        ),
        migrations.CreateModel(
            name='ResultEvent',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('event_type', models.IntegerField(default=0, choices=[(0, b'Not sent'), (1, b'Recived'), (2, b'Open'), (3, b'Submit')])),
                ('timestamp', models.DateTimeField(null=True)),
                ('userAgent', models.CharField(max_length=255, null=True)),
                ('ip', models.GenericIPAddressField(null=True)),
                ('login', models.CharField(max_length=100, null=True)),
                ('password', models.CharField(max_length=100, null=True)),
                ('raw_data', models.TextField(null=True)),
                ('counter', models.IntegerField(default=1)),
            ],
        ),
        migrations.CreateModel(
            name='ScheduleInterval',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=100, null=True)),
                ('batch_size', models.IntegerField(null=True)),
                ('batch_interval', models.IntegerField(null=True)),
                ('start_type', models.CharField(default=b'now', max_length=20)),
                ('start_at', models.DateTimeField(null=True)),
                ('interval', models.ForeignKey(to='djcelery.CrontabSchedule', null=True)),
            ],
        ),
        migrations.CreateModel(
            name='SmtpLog',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('date_created', models.DateTimeField(auto_now_add=True, null=True)),
                ('error', models.CharField(max_length=255, null=True)),
                ('target_email', models.CharField(max_length=255, null=True)),
                ('campaign_name', models.CharField(max_length=255, null=True)),
                ('campaign_link', models.CharField(max_length=255, null=True)),
                ('client_name', models.CharField(max_length=255, null=True)),
                ('engagement', models.ForeignKey(to='client.Engagement', null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Target',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('email', models.EmailField(max_length=50, null=True)),
                ('firstname', models.CharField(max_length=50, null=True, blank=True)),
                ('lastname', models.CharField(max_length=50, null=True, blank=True)),
                ('timezone', models.CharField(max_length=10, null=True, blank=True)),
                ('result', models.ManyToManyField(to='client.Result')),
            ],
        ),
        migrations.CreateModel(
            name='TargetDatum',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('shortCode', models.CharField(max_length=100, null=True)),
                ('datumLabel', models.CharField(max_length=100, null=True)),
                ('datumValue', models.CharField(max_length=100, null=True)),
                ('target', models.ForeignKey(to='client.Target', null=True)),
            ],
        ),
        migrations.CreateModel(
            name='TargetList',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('nickname', models.CharField(max_length=100, null=True)),
                ('description', models.CharField(max_length=100, null=True)),
                ('client', models.ForeignKey(to='client.Client', null=True)),
                ('target', models.ManyToManyField(to='client.Target')),
            ],
        ),
        migrations.CreateModel(
            name='TaskScheduler',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('interval', models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, to='client.ScheduleInterval', null=True)),
                ('periodic_task', models.ForeignKey(to='djcelery.PeriodicTask')),
            ],
        ),
        migrations.AddField(
            model_name='result',
            name='result_event',
            field=models.ManyToManyField(to='client.ResultEvent'),
        ),
        migrations.AddField(
            model_name='engagement',
            name='landing_page',
            field=models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, to='client.LandingPage', null=True),
        ),
        migrations.AddField(
            model_name='engagement',
            name='redirect_page',
            field=models.ForeignKey(related_name='redirect_page', on_delete=django.db.models.deletion.SET_NULL, to='client.LandingPage', null=True),
        ),
        migrations.AddField(
            model_name='engagement',
            name='schedule',
            field=models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, to='client.TaskScheduler', null=True),
        ),
        migrations.AddField(
            model_name='engagement',
            name='target_lists',
            field=models.ManyToManyField(to='client.TargetList'),
        ),
        migrations.AddField(
            model_name='campaign',
            name='client',
            field=models.ForeignKey(to='client.Client', null=True),
        ),
    ]
