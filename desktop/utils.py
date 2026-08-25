# utils.py
"""Utilitaires partagés pour l'application desktop."""

import threading


def run_async(root, work_fn, on_success=None, on_error=None):
    """
    Exécute work_fn() dans un thread séparé pour ne pas bloquer l'UI Tkinter,
    puis transmet le résultat (ou l'exception) au thread principal via root.after().
    """

    def runner():
        try:
            result = work_fn()
        except Exception as e:  # noqa: BLE001
            if on_error:
                try:
                    root.after(0, lambda err=e: on_error(err))
                except RuntimeError:
                    pass
            return
        if on_success:
            try:
                root.after(0, lambda res=result: on_success(res))
            except RuntimeError:
                pass

    threading.Thread(target=runner, daemon=True).start()


# ── Constantes de style — alignées sur la palette de l'app web (base.html) ──
COLORS = {
    "bg":          "#f2f4f8",   # --surface
    "bg_alt":      "#e8eaf0",   # --surface-alt
    "card":        "#ffffff",   # --white
    "primary":     "#2962ff",   # --blue
    "primary_dim": "#e6ecff",   # --blue-dim
    "dark":        "#0b0e17",   # --ink
    "text":        "#1c2235",   # --ink-soft
    "muted":       "#374163",   # --ink-muted
    "muted_light": "#8890ab",   # dérivé (entre --ink-muted et --surface)
    "border":      "#dde1ec",   # --line
    "border_soft": "#eceef5",   # --line-soft
    "success":     "#00c27a",   # --green
    "success_dim": "#e4f9f1",   # --green-dim
    "success_text": "#007a4d",  # --green-text
    "error":       "#e8344a",   # --red
    "error_dim":   "#fdeaed",   # --red-dim
    "error_text":  "#b01f32",   # --red-text
    "warning":     "#f5a623",   # --amber
    "warning_dim": "#fef4e3",   # --amber-dim
    "warning_text": "#a86f00",  # --amber-text
    "primary_text": "#1940cc",  # --blue-text
    "garde":       "#c77d00",   # nuance ambre plus soutenue, pour distinguer la garde d'un simple avertissement
    "garde_bg":    "#fef4e3",   # --amber-dim
}

# Segoe UI reste la police système : Tkinter ne peut pas charger la police web
# (Syne, chargée depuis Google Fonts) sans embarquer et enregistrer la police
# manuellement au démarrage de l'exe. Segoe UI est la police système Windows
# la plus proche en poids/esprit (géométrique, sans-serif).
FONT_FAMILY = "Segoe UI"
