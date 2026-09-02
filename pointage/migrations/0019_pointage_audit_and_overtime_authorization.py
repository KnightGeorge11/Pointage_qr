from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [('pointage', '0018_scan_client_event_id')]
    operations = [
        migrations.AddField(
            model_name='pointage', name='heures_supplementaires_autorisees',
            field=models.BooleanField(default=False, help_text='Une heure supplémentaire calculée n’est comptabilisée qu’après validation RH.', verbose_name='Heures supplémentaires autorisées'),
        ),
        migrations.AddField(
            model_name='pointage', name='heures_supplementaires_autorisees_par',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='heures_supplementaires_validees', to='pointage.customuser'),
        ),
        migrations.AddField(
            model_name='pointage', name='date_autorisation_heures_supplementaires',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='pointage', name='motif_autorisation_heures_supplementaires',
            field=models.TextField(blank=True),
        ),
        migrations.CreateModel(
            name='PointageAudit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(choices=[('create','Création'),('update','Modification'),('delete','Suppression')], max_length=10)),
                ('avant', models.JSONField(blank=True, default=dict)),
                ('apres', models.JSONField(blank=True, default=dict)),
                ('motif', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('administrateur', models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='pointages_audites', to='pointage.customuser')),
                ('pointage', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='audit_entries', to='pointage.pointage')),
            ],
            options={
                'verbose_name': 'Audit de pointage',
                'verbose_name_plural': 'Audits de pointage',
                'ordering': ['-created_at'],
                'indexes': [models.Index(fields=['pointage','created_at'], name='pointage_po_pointag_5b5c2d_idx'), models.Index(fields=['administrateur','created_at'], name='pointage_po_adminis_8a1b12_idx')],
            },
        ),
    ]
