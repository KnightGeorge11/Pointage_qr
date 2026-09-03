from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("pointage", "0020_enforce_overtime_authorization"),
    ]

    operations = [
        migrations.RenameIndex(
            model_name="pointageaudit",
            old_name="pointage_po_pointag_5b5c2d_idx",
            new_name="pointage_po_pointag_feef60_idx",
        ),
        migrations.RenameIndex(
            model_name="pointageaudit",
            old_name="pointage_po_adminis_8a1b12_idx",
            new_name="pointage_po_adminis_0111de_idx",
        ),
    ]
