# Generated by Django 2.2.13 on 2021-04-07 12:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('waveforms', '0008_usersettings_background_color'),
    ]

    operations = [
        migrations.AddField(
            model_name='usersettings',
            name='signal_std',
            field=models.FloatField(default=2.0),
        ),
    ]
