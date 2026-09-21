from django.db import migrations, models


def remove_obsolete_account_requests(apps, schema_editor):
    DemandeModification = apps.get_model('pointage', 'DemandeModification')
    DemandeModification.objects.filter(cible='utilisateur').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('pointage', '0025_alter_demandemodification_cible'),
    ]

    operations = [
        migrations.RunPython(
            remove_obsolete_account_requests,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name='demandemodification',
            name='cible',
            field=models.CharField(
                choices=[
                    ('employe', 'Employé'),
                    ('site', 'Site'),
                    ('poste', 'Poste'),
                ],
                max_length=20,
            ),
        ),
    ]
