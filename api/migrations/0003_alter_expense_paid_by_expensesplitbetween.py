# Generated by Django 5.1.5 on 2025-06-02 09:53

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0002_friend_request_delete_friendrequest'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='expense',
            name='paid_by',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.CreateModel(
            name='ExpenseSplitBetween',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('owe_id', models.CharField(max_length=100)),
                ('expense', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='api.expense')),
            ],
        ),
    ]
