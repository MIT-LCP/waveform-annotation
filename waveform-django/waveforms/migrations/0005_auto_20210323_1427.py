# Generated by Django 2.2.13 on 2021-03-23 18:27

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('waveforms', '0004_usersettings'),
    ]

    operations = [
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('username', models.CharField(default='', max_length=150, unique=True)),
                ('join_date', models.DateField(auto_now_add=True)),
            ],
        ),
        migrations.AlterField(
            model_name='annotation',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='annotation', to='waveforms.User'),
        ),
        migrations.AlterField(
            model_name='usersettings',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='settings', to='waveforms.User'),
        ),
    ]
