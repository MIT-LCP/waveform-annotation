# Generated by Django 2.2.13 on 2021-08-03 01:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('waveforms', '0013_annotation_project'),
    ]

    operations = [
        migrations.AlterField(
            model_name='usersettings',
            name='signal_std',
            field=models.FloatField(default=3.0),
        ),
    ]
