# Generated by Django 5.1.5 on 2025-06-08 11:19

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0008_expense_created_at_settlement_created_at'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='settlement',
            name='created_at',
        ),
    ]
