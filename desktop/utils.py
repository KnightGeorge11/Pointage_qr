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


# ── Constantes de style (équivalent palette mobile) ────────────────────────
COLORS = {
    "bg": "#f5f5f7",
    "card": "#ffffff",
    "primary": "#007AFF",
    "dark": "#1a1a1a",
    "text": "#333333",
    "muted": "#999999",
    "muted_light": "#bbbbbb",
    "border": "#e5e5e5",
    "success": "#34C759",
    "error": "#FF3B30",
    "warning": "#F59E0B",
    "garde": "#D97706",
    "garde_bg": "#FEF3C7",
}

FONT_FAMILY = "Segoe UI"
