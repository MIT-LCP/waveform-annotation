# Generated by Django 2.2.13 on 2021-07-30 03:22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('waveforms', '0012_usersettings_n_ekg_sigs'),
    ]

    operations = [
        migrations.AddField(
            model_name='annotation',
            name='project',
            field=models.CharField(default='2015_data', max_length=50),
            preserve_default=False,
        ),
    ]
