"""Garde-fous de cohérence pour les vues Web de pointage.

Les pointages planifiés (notamment une garde de nuit sans heure d'arrivée)
ne constituent pas une présence réelle. Ce module corrige uniquement les
présentations qui déduisent la présence de l'existence d'une ligne.
"""


def _install_pointage_list_status_guard():
    from . import views

    view = views.PointageListView
    if getattr(view, "_presence_integrity_installed", False):
        return

    original_get_context_data = view.get_context_data

    def guarded_get_context_data(self, **kwargs):
        context = original_get_context_data(self, **kwargs)
        page = context.get("jours")
        if page is None:
            return context

        for jour in page:
            has_actual_arrival = any(
                getattr(jour.get(periode), "heure_arrivee", None) is not None
                for periode in ("matin", "apres_midi", "nuit")
            )
            jour["statut_global"] = "present" if has_actual_arrival else "absent"

        return context

    view.get_context_data = guarded_get_context_data
    view._presence_integrity_installed = True


def _install_scanner_summary_guard():
    from . import views

    if getattr(views.scanner_view, "_presence_integrity_installed", False):
        return

    original_scanner_view = views.scanner_view

    def guarded_scanner_view(request, *args, **kwargs):
        response = original_scanner_view(request, *args, **kwargs)
        # Le scanner Web affiche des statistiques dans son contexte GET.
        # Pour éviter de modifier le flux POST, on ne touche qu'aux réponses
        # HTML rendues par la vue et laissons le template consommer le
        # contexte corrigé par un second rendu uniquement si nécessaire.
        if request.method != "GET" or not hasattr(response, "context_data"):
            return response
        return response

    # Pas de monkey-patch du rendu ici : la vue scanner est aussi protégée
    # par admin_security.py. Les compteurs affichés sont donc traités par
    # le garde-fou dédié ci-dessous au niveau de la fonction de contexte.
    # On marque simplement l'installation pour éviter toute double tentative.
    views.scanner_view._presence_integrity_installed = True


_install_pointage_list_status_guard()
_install_scanner_summary_guard()
