# Generated by Django 2.2.13 on 2021-11-16 17:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('waveforms', '0022_user_practice_status'),
    ]

    operations = [
        migrations.AlterField(
            model_name='usersettings',
            name='fig_height',
            field=models.FloatField(default=690.0),
        ),
    ]
