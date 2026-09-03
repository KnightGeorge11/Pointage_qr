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


# ── Design System Pointage QR ────────────────────────────────────────────────
# Tokens alignés sur le Web et le mobile. Les écrans desktop doivent référencer
# COLORS plutôt que définir leurs propres couleurs.
COLORS = {
    "bg":           "#F8FAFC",
    "bg_alt":       "#F1F5F9",
    "card":         "#FFFFFF",
    "primary":      "#2563EB",
    "primary_dim":  "#EFF6FF",
    "dark":         "#0F172A",
    "text":         "#334155",
    "muted":        "#64748B",
    "muted_light":  "#94A3B8",
    "border":       "#E2E8F0",
    "border_soft":  "#F1F5F9",
    "success":      "#22C55E",
    "success_dim":  "#F0FDF4",
    "success_text": "#15803D",
    "error":        "#EF4444",
    "error_dim":    "#FEF2F2",
    "error_text":   "#DC2626",
    "warning":      "#F59E0B",
    "warning_dim":  "#FFFBEB",
    "warning_text": "#D97706",
    "primary_text": "#1D4ED8",
    "garde":        "#D97706",
    "garde_bg":     "#FFFBEB",
}

# Segoe UI reste la police système Windows du client Tkinter.
FONT_FAMILY = "Segoe UI"
