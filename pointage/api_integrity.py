"""Garde-fous d'intégrité pour les API de pointage.

La création REST reste autorisée car PointageSerializer.create() délègue
elle-même au moteur central process_scan(). En revanche, les opérations de
modification et suppression directes sont interdites : les corrections
passent par les procédures RH dédiées.
"""

from rest_framework.response import Response
from rest_framework import status

from . import views


def _deny_update(self, request, *args, **kwargs):
    return Response(
        {
            "detail": (
                "Les pointages sont des traces immuables. "
                "Une correction doit passer par la procédure RH dédiée."
            )
        },
        status=status.HTTP_403_FORBIDDEN,
    )


def _deny_destroy(self, request, *args, **kwargs):
    return Response(
        {"detail": "Les pointages sont des traces immuables et ne peuvent pas être supprimés."},
        status=status.HTTP_403_FORBIDDEN,
    )


def install():
    viewset = getattr(views, "PointageViewSet", None)
    if viewset is None or getattr(viewset, "_integrity_hardened", False):
        return

    # create() est volontairement conservé : PointageSerializer.create()
    # appelle process_scan(), donc ce chemin partage la même state machine,
    # les mêmes contrôles horaires, l'anti-doublon et les règles de garde.
    # Interdire create() ici casserait les tests de parité API/mobile et les
    # usages RH existants sans apporter de sécurité supplémentaire.
    viewset.update = _deny_update
    viewset.partial_update = _deny_update
    viewset.destroy = _deny_destroy
    viewset._integrity_hardened = True


install()
