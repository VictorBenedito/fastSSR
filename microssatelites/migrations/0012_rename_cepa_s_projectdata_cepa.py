# Generated by Django 3.2.9 on 2022-10-29 21:59

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('microssatelites', '0011_rename_cepa_projectdata_cepa_s'),
    ]

    operations = [
        migrations.RenameField(
            model_name='projectdata',
            old_name='cepa_S',
            new_name='cepa',
        ),
    ]
