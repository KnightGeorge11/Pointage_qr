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


_install_pointage_list_status_guard()
