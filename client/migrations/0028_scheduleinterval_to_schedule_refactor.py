# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.contrib.postgres.fields
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('client', '0027_slackhook'),
    ]

    operations = [
        migrations.CreateModel(
            name='Schedule',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=255, null=True)),
                ('description', models.TextField(null=True, blank=True)),
                ('is_default', models.BooleanField(default=True)),
                ('interval', models.IntegerField(default=10, blank=True)),
                ('excluded_dates', django.contrib.postgres.fields.ArrayField(default=list, size=None, base_field=models.DateField(blank=True), blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='ScheduleWindow',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('day_of_the_week', models.CharField(default=b'monday', max_length=9, null=True, blank=True, choices=[(b'monday', b'Monday'), (b'tuesday', b'Tuesday'), (b'wednesday', b'Wednesday'), (b'thursday', b'Thursday'), (b'friday', b'Friday'), (b'saturday', b'Saturday'), (b'sunday', b'Sunday')])),
                ('open_time', models.TimeField(default=b'00:00:00')),
                ('close_time', models.TimeField(default=b'23:59:59')),
                ('schedule', models.ForeignKey(related_name='windows', to='client.Schedule')),
            ],
        ),
        migrations.RemoveField(
            model_name='engagement',
            name='interval',
        ),
        migrations.AddField(
            model_name='engagement',
            name='internal_error',
            field=models.TextField(default=b'', blank=True),
        ),
        migrations.AddField(
            model_name='engagement',
            name='start_date',
            field=models.DateField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='engagement',
            name='start_time',
            field=models.TimeField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='engagement',
            name='start_type',
            field=models.CharField(default=b'immediate', max_length=15, choices=[(b'immediate', b'Immediate'), (b'countdown', b'Countdown'), (b'specific_date', b'Specific date')]),
        ),
        migrations.AlterField(
            model_name='vectoremail',
            name='state',
            field=models.SmallIntegerField(default=0, choices=[(0, b'Unscheduled'), (1, b'Ready'), (2, b'Paused'), (3, b'Error'), (4, b'Sent'), (5, b'Send Missed')]),
        ),
        migrations.DeleteModel(
            name='ScheduleInterval',
        ),
        migrations.AddField(
            model_name='engagement',
            name='schedule',
            field=models.ForeignKey(related_name='engagement', on_delete=django.db.models.deletion.SET_NULL, to='client.Schedule', null=True),
        ),
    ]
