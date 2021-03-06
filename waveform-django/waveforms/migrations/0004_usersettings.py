# Generated by Django 2.2.13 on 2021-03-04 13:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('waveforms', '0003_auto_20201110_1244'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserSettings',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('user', models.CharField(default='', max_length=150, unique=True)),
                ('fig_height', models.FloatField(default=725)),
                ('fig_width', models.FloatField(default=875)),
                ('margin_left', models.FloatField(default=0)),
                ('margin_top', models.FloatField(default=25)),
                ('margin_right', models.FloatField(default=0)),
                ('margin_bottom', models.FloatField(default=0)),
                ('grid_color', models.TextField(default='#ff3c3c')),
                ('sig_color', models.TextField(default='#000000')),
                ('sig_thickness', models.FloatField(default=1.5)),
                ('ann_color', models.TextField(default='#3c3cc8')),
                ('grid_delta_major', models.FloatField(default=0.2)),
                ('max_y_labels', models.IntegerField(default=8)),
                ('down_sample_ekg', models.IntegerField(default=8)),
                ('down_sample', models.IntegerField(default=16)),
                ('time_range_min', models.FloatField(default=40)),
                ('time_range_max', models.FloatField(default=10)),
                ('window_size_min', models.FloatField(default=10)),
                ('window_size_max', models.FloatField(default=1)),
            ],
        ),
    ]
