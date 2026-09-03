"""Garde-fous d'intégrité pour les API de pointage.

Les pointages sont des traces métier : leur création doit passer par le
moteur central process_scan(), et leur modification/suppression par les
procédures RH dédiées (demandes/corrections). Le ViewSet REST ne doit donc
pas offrir un raccourci permettant de fabriquer ou réécrire une trace.
"""

from rest_framework.response import Response
from rest_framework import status

from . import views


def _deny_create(self, request, *args, **kwargs):
    return Response(
        {
            "detail": (
                "La création directe d'un pointage est interdite. "
                "Utilisez le moteur de scan centralisé."
            )
        },
        status=status.HTTP_405_METHOD_NOT_ALLOWED,
    )


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

    viewset.create = _deny_create
    viewset.update = _deny_update
    viewset.partial_update = _deny_update
    # destroy est également protégé par admin_hardening ; on le fixe ici pour
    # que l'intégrité REST reste garantie même si l'ordre de chargement change.
    viewset.destroy = _deny_destroy
    viewset._integrity_hardened = True


install()
