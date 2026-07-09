# pointage/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Employe, Pointage
from django.utils import timezone
from datetime import datetime

# Vous pouvez ajouter des signaux ici si nécessaire
# Par exemple, pour créer automatiquement des pointages

@receiver(post_save, sender=Employe)
def generer_qr_code_si_manquant(sender, instance, created, **kwargs):
    """S'assure qu'un QR code est généré pour chaque employé"""
    if created and not instance.qr_code:
        instance.generer_qr_code()
        instance.save()