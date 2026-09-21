# Generated manually for the public holiday reference calendar.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pointage', '0026_remove_user_account_target'),
    ]

    operations = [
        migrations.CreateModel(
            name='JourFerie',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('date', models.DateField(unique=True, verbose_name='Date')),
                ('nom', models.CharField(max_length=150, verbose_name='Libellé')),
                ('actif', models.BooleanField(default=True, verbose_name='Actif')),
            ],
            options={
                'verbose_name': 'Jour férié',
                'verbose_name_plural': 'Jours fériés',
                'ordering': ['date'],
            },
        ),
    ]
