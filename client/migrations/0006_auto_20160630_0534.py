# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('djcelery', '0001_initial'),
        ('client', '0005_auto_20160311_1933'),
    ]

    operations = [
        migrations.CreateModel(
            name='VectorEmail',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('custom_state', models.BooleanField(default=False)),
                ('state', models.SmallIntegerField(default=0, choices=[(0, b'Not Sent'), (1, b'Pending'), (2, b'Paused'), (3, b'Error'), (4, b'Sent'), (5, b'Send Missed')])),
                ('custom_email_template', models.BooleanField(default=False)),
                ('custom_landing_page', models.BooleanField(default=False)),
                ('custom_redirect_page', models.BooleanField(default=False)),
                ('custom_send_at', models.BooleanField(default=False)),
                ('send_at', models.DateTimeField(null=True)),
                ('sent_timestamp', models.DateTimeField(null=True)),
                ('error', models.TextField(default=b'', null=True, blank=True)),
                ('email_template', models.ForeignKey(related_name='vector_email', on_delete=django.db.models.deletion.SET_NULL, to='client.EmailTemplate', null=True)),
            ],
        ),
        migrations.RemoveField(
            model_name='result',
            name='engagement',
        ),
        migrations.RemoveField(
            model_name='result',
            name='result_event',
        ),
        migrations.RemoveField(
            model_name='smtplog',
            name='engagement',
        ),
        migrations.RemoveField(
            model_name='taskscheduler',
            name='interval',
        ),
        migrations.RemoveField(
            model_name='taskscheduler',
            name='periodic_task',
        ),
        migrations.RemoveField(
            model_name='engagement',
            name='schedule',
        ),
        migrations.RemoveField(
            model_name='resultevent',
            name='counter',
        ),
        migrations.RemoveField(
            model_name='scheduleinterval',
            name='interval',
        ),
        migrations.RemoveField(
            model_name='target',
            name='result',
        ),
        migrations.AddField(
            model_name='engagement',
            name='interval',
            field=models.ForeignKey(related_name='engagement', on_delete=django.db.models.deletion.SET_NULL, to='client.ScheduleInterval', null=True),
        ),
        migrations.AddField(
            model_name='engagement',
            name='state',
            field=models.SmallIntegerField(default=0, editable=False, choices=[(0, b'Not Launched'), (1, b'In Progress'), (2, b'Paused'), (3, b'Error'), (4, b'Complete')]),
        ),
        migrations.AddField(
            model_name='engagement',
            name='url_key',
            field=models.CharField(max_length=32, null=True, editable=False),
        ),
        migrations.AddField(
            model_name='scheduleinterval',
            name='time_between_batches',
            field=models.IntegerField(null=True),
        ),
        migrations.AlterField(
            model_name='client',
            name='default_time_zone',
            field=models.CharField(max_length=32, null=True, choices=[(b'Etc/GMT+12', b'UTC-12:00'), (b'Etc/GMT+11', b'UTC-11:00'), (b'Etc/GMT+10', b'UTC-10:00'), (b'Etc/GMT+9', b'UTC-09:00'), (b'Etc/GMT+8', b'UTC-08:00'), (b'Etc/GMT+7', b'UTC-07:00'), (b'Etc/GMT+6', b'UTC-06:00'), (b'Etc/GMT+5', b'UTC-05:00'), (b'Etc/GMT+4', b'UTC-04:00'), (b'Etc/GMT+3', b'UTC-03:00'), (b'Etc/GMT+2', b'UTC-02:00'), (b'Etc/GMT+1', b'UTC-01:00'), (b'Etc/GMT+0', b'UTC+00:00'), (b'Etc/GMT-1', b'UTC+01:00'), (b'Etc/GMT-2', b'UTC+02:00'), (b'Etc/GMT-3', b'UTC+03:00'), (b'Etc/GMT-4', b'UTC+04:00'), (b'Etc/GMT-5', b'UTC+05:00'), (b'Etc/GMT-6', b'UTC+06:00'), (b'Etc/GMT-7', b'UTC+07:00'), (b'Etc/GMT-8', b'UTC+08:00'), (b'Etc/GMT-9', b'UTC+09:00'), (b'Etc/GMT-10', b'UTC+10:00'), (b'Etc/GMT-11', b'UTC+11:00'), (b'Etc/GMT-12', b'UTC+12:00'), (b'Etc/GMT-13', b'UTC+13:00'), (b'Etc/GMT-14', b'UTC+14:00')]),
        ),
        migrations.AlterField(
            model_name='engagement',
            name='email_template',
            field=models.ForeignKey(related_name='engagement', on_delete=django.db.models.deletion.SET_NULL, to='client.EmailTemplate', null=True),
        ),
        migrations.AlterField(
            model_name='engagement',
            name='landing_page',
            field=models.ForeignKey(related_name='landing_page_engagement', on_delete=django.db.models.deletion.SET_NULL, to='client.LandingPage', null=True),
        ),
        migrations.AlterField(
            model_name='engagement',
            name='redirect_page',
            field=models.ForeignKey(related_name='redirect_page_engagement', on_delete=django.db.models.deletion.SET_NULL, to='client.LandingPage', null=True),
        ),
        migrations.AlterField(
            model_name='landingpage',
            name='page_type',
            field=models.CharField(default=b'page', max_length=10, choices=[(b'url', b'URL'), (b'page', b'Scraped Page'), (b'manual', b'Manual')]),
        ),
        migrations.AlterField(
            model_name='target',
            name='email',
            field=models.EmailField(max_length=254, null=True),
        ),
        migrations.AlterField(
            model_name='target',
            name='timezone',
            field=models.CharField(blank=True, max_length=32, null=True, choices=[(b'Etc/GMT+12', b'UTC-12:00'), (b'Etc/GMT+11', b'UTC-11:00'), (b'Etc/GMT+10', b'UTC-10:00'), (b'Etc/GMT+9', b'UTC-09:00'), (b'Etc/GMT+8', b'UTC-08:00'), (b'Etc/GMT+7', b'UTC-07:00'), (b'Etc/GMT+6', b'UTC-06:00'), (b'Etc/GMT+5', b'UTC-05:00'), (b'Etc/GMT+4', b'UTC-04:00'), (b'Etc/GMT+3', b'UTC-03:00'), (b'Etc/GMT+2', b'UTC-02:00'), (b'Etc/GMT+1', b'UTC-01:00'), (b'Etc/GMT+0', b'UTC+00:00'), (b'Etc/GMT-1', b'UTC+01:00'), (b'Etc/GMT-2', b'UTC+02:00'), (b'Etc/GMT-3', b'UTC+03:00'), (b'Etc/GMT-4', b'UTC+04:00'), (b'Etc/GMT-5', b'UTC+05:00'), (b'Etc/GMT-6', b'UTC+06:00'), (b'Etc/GMT-7', b'UTC+07:00'), (b'Etc/GMT-8', b'UTC+08:00'), (b'Etc/GMT-9', b'UTC+09:00'), (b'Etc/GMT-10', b'UTC+10:00'), (b'Etc/GMT-11', b'UTC+11:00'), (b'Etc/GMT-12', b'UTC+12:00'), (b'Etc/GMT-13', b'UTC+13:00'), (b'Etc/GMT-14', b'UTC+14:00')]),
        ),
        migrations.DeleteModel(
            name='Result',
        ),
        migrations.DeleteModel(
            name='SmtpLog',
        ),
        migrations.DeleteModel(
            name='TaskScheduler',
        ),
        migrations.AddField(
            model_name='vectoremail',
            name='engagement',
            field=models.ForeignKey(related_name='vector_email', to='client.Engagement', null=True),
        ),
        migrations.AddField(
            model_name='vectoremail',
            name='landing_page',
            field=models.ForeignKey(related_name='landing_page_vector_email', on_delete=django.db.models.deletion.SET_NULL, to='client.LandingPage', null=True),
        ),
        migrations.AddField(
            model_name='vectoremail',
            name='periodic_task',
            field=models.ForeignKey(to='djcelery.PeriodicTask', null=True),
        ),
        migrations.AddField(
            model_name='vectoremail',
            name='redirect_page',
            field=models.ForeignKey(related_name='redirect_page_vector_email', on_delete=django.db.models.deletion.SET_NULL, to='client.LandingPage', null=True),
        ),
        migrations.AddField(
            model_name='vectoremail',
            name='result_event',
            field=models.ManyToManyField(to='client.ResultEvent'),
        ),
        migrations.AddField(
            model_name='vectoremail',
            name='target',
            field=models.ForeignKey(related_name='vector_email', to='client.Target', null=True),
        ),
    ]
