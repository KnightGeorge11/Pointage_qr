# pointage/mixins.py
from django.contrib.auth.mixins import LoginRequiredMixin


class DemandeRequiredMixin(LoginRequiredMixin):
    """
    Remplace AdminCodeRequiredMixin.
    L'utilisateur doit être connecté.
    Les actions POST ne s'appliquent pas directement en base —
    elles créent une DemandeModification en attente de validation admin.
    """

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['mode'] = 'demande'
        return context


class AdminCodeRequiredMixin(DemandeRequiredMixin):
    """
    Alias conservé pour ne pas casser les imports existants.
    Redirige vers le flux demande au lieu de demander un code admin.
    """
    pass


class AdminCodeRequiredForGetMixin(DemandeRequiredMixin):
    """
    Alias conservé pour ne pas casser les imports existants (suppressions).
    Redirige vers le flux demande au lieu de demander un code admin.
    """
    pass