# screens/history.py
"""
Journal du jour — tous les scans de la journée tirés du serveur.

Endpoint utilisé :
  GET /api/mobile/pointages/today/?site_id=N&date=YYYY-MM-DD

Affichage :
  - Tous les pointages du jour (ou d'une date choisie)
  - Filtre par site (tous les sites OU site sélectionné)
  - Auto-refresh toutes les 30 secondes
  - Par ligne : Nom Prénom, heure arrivée → départ, période, statut
"""

import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta
import api_client
from utils import COLORS, run_async
import logging

REFRESH_INTERVAL_MS = 30_000   # 30 secondes

PERIODE_LABEL = {
    "matin":      ("Matin",      COLORS["warning_text"], COLORS["warning_dim"]),
    "apres_midi": ("Après-midi", COLORS["primary_text"], COLORS["primary_dim"]),
    "nuit":       ("Nuit",       "#7c3aed",               "#ede9fe"),
}
STATUT_LABEL = {
    "present": ("Présent",   COLORS["success"]),
    "retard":  ("Retard",    COLORS["error"]),
    "absent":  ("Absent",    COLORS["muted"]),
    "congé":   ("Congé",     COLORS["muted"]),
    "maladie": ("Maladie",   COLORS["muted"]),
}


def fmt_heure(t):
    return t[:5] if t else "—"


def fmt_statut_presence(p: dict) -> tuple[str, str]:
    """Retourne (texte, couleur) selon arrivée/départ."""
    if p.get("heure_arrivee") and not p.get("heure_depart"):
        return "En cours", COLORS["success"]
    if p.get("heure_arrivee") and p.get("heure_depart"):
        return "Parti", COLORS["muted"]
    return "Absent", COLORS["error"]


class HistoryScreen(tk.Frame):
    TITLE = "Journal du jour"

    def __init__(self, parent, app):
        super().__init__(parent, bg=COLORS["bg"])
        self.app = app
        self.pointages = []
        self._refresh_job = None
        self._loading = False
        self._last_refresh = None
        self._selected_site_id = None   # None = tous les sites
        self._sites_cache = []          # [(id, nom), ...]
        self._date = datetime.now().date()
        self._build_ui()

    # ── Construction UI ───────────────────────────────────────────────
    def _build_ui(self):
        # ── Barre supérieure ─────────────────────────────────────────
        top = tk.Frame(self, bg=COLORS["bg"])
        top.pack(fill="x", padx=20, pady=(16, 4))

        tk.Button(top, text="← Retour", bg=COLORS["bg"], fg=COLORS["primary"],
                  relief="flat", bd=0, font=("Segoe UI", 10, "bold"),
                  command=self.app.go_back, cursor="hand2").pack(side="left")

        self.refresh_btn = tk.Button(top, text="⟳ Actualiser", bg=COLORS["dark"], fg="white",
                                      relief="flat", padx=12, pady=5, font=("Segoe UI", 9, "bold"),
                                      command=self._manual_refresh, cursor="hand2")
        self.refresh_btn.pack(side="right")

        # ── Titre + sous-titre ───────────────────────────────────────
        title_row = tk.Frame(self, bg=COLORS["bg"])
        title_row.pack(fill="x", padx=20, pady=(4, 0))
        tk.Label(title_row, text="Journal du jour", bg=COLORS["bg"], fg=COLORS["dark"],
                 font=("Segoe UI", 20, "bold")).pack(side="left")

        self.count_label = tk.Label(title_row, text="", bg=COLORS["bg"], fg=COLORS["muted"],
                                     font=("Segoe UI", 10))
        self.count_label.pack(side="left", padx=(12, 0))

        # ── Barre de filtres ─────────────────────────────────────────
        filters = tk.Frame(self, bg=COLORS["bg"])
        filters.pack(fill="x", padx=20, pady=(10, 0))

        # Sélecteur de date
        tk.Label(filters, text="Date :", bg=COLORS["bg"], fg=COLORS["muted"],
                 font=("Segoe UI", 9)).pack(side="left")

        nav_left = tk.Button(filters, text="◀", relief="flat", bg=COLORS["bg"], fg=COLORS["dark"],
                              font=("Segoe UI", 10), command=self._prev_day, cursor="hand2", padx=4)
        nav_left.pack(side="left", padx=(4, 0))

        self.date_label = tk.Button(filters, relief="flat", bg=COLORS["card"], fg=COLORS["dark"],
                                     font=("Segoe UI", 10), padx=10, pady=4,
                                     command=self._go_today, cursor="hand2")
        self.date_label.pack(side="left", padx=2)
        self._update_date_label()

        nav_right = tk.Button(filters, text="▶", relief="flat", bg=COLORS["bg"], fg=COLORS["dark"],
                               font=("Segoe UI", 10), command=self._next_day, cursor="hand2", padx=4)
        nav_right.pack(side="left", padx=(0, 16))

        # Sélecteur de site
        tk.Label(filters, text="Site :", bg=COLORS["bg"], fg=COLORS["muted"],
                 font=("Segoe UI", 9)).pack(side="left")
        self.site_var = tk.StringVar(value="Tous les sites")
        self.site_combo = ttk.Combobox(filters, textvariable=self.site_var, state="readonly",
                                        width=22, font=("Segoe UI", 9))
        self.site_combo.pack(side="left", padx=(4, 0))
        self.site_combo.bind("<<ComboboxSelected>>", self._on_site_selected)

        # Indicateur de dernier refresh
        self.last_refresh_label = tk.Label(self, text="", bg=COLORS["bg"], fg=COLORS["muted_light"],
                                            font=("Segoe UI", 8))
        self.last_refresh_label.pack(anchor="e", padx=20, pady=(4, 4))

        # ── Liste scrollable ─────────────────────────────────────────
        list_container = tk.Frame(self, bg=COLORS["bg"])
        list_container.pack(fill="both", expand=True, padx=20, pady=(0, 16))
        self.canvas = tk.Canvas(list_container, bg=COLORS["bg"], highlightthickness=0)
        scrollbar = tk.Scrollbar(list_container, orient="vertical", command=self.canvas.yview)
        self.list_frame = tk.Frame(self.canvas, bg=COLORS["bg"])
        self.list_frame.bind("<Configure>",
                              lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.list_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Scroll à la molette
        self.canvas.bind_all("<MouseWheel>",
                              lambda e: self.canvas.yview_scroll(-1*(e.delta//120), "units"))

    # ── Cycle de vie ──────────────────────────────────────────────────
    def on_enter(self, **params):
        self._cancel_refresh()
        self._date = datetime.now().date()
        self._update_date_label()

        # Pré-remplir le site depuis le site sélectionné dans l'app
        if self.app.selected_site:
            self._selected_site_id = self.app.selected_site["id"]
        else:
            self._selected_site_id = None

        self._load_sites_then_data()
        self._schedule_refresh()

    def _cancel_refresh(self):
        if self._refresh_job:
            self.after_cancel(self._refresh_job)
            self._refresh_job = None

    def _schedule_refresh(self):
        self._cancel_refresh()
        self._refresh_job = self.after(REFRESH_INTERVAL_MS, self._auto_refresh)

    def _auto_refresh(self):
        if self._date == datetime.now().date():  # seulement si on affiche aujourd'hui
            self._fetch_data()
        self._schedule_refresh()

    def _manual_refresh(self):
        self._cancel_refresh()
        self._fetch_data()
        self._schedule_refresh()

    # ── Chargement des sites pour le combobox ─────────────────────────
    def _load_sites_then_data(self):
        def work():
            return api_client.get_sites()

        def on_success(sites):
            self._sites_cache = sites
            options = ["Tous les sites"] + [s["nom"] for s in sites]
            self.site_combo["values"] = options
            # Sélectionner le bon site dans le combobox
            if self._selected_site_id:
                for s in sites:
                    if s["id"] == self._selected_site_id:
                        self.site_var.set(s["nom"])
                        break
            else:
                self.site_var.set("Tous les sites")
            self._fetch_data()

        def on_error(e):
            self.site_combo["values"] = ["Tous les sites"]
            self.site_var.set("Tous les sites")
            self._fetch_data()

        run_async(self.app, work, on_success=on_success, on_error=on_error)

    def _on_site_selected(self, event=None):
        val = self.site_var.get()
        if val == "Tous les sites":
            self._selected_site_id = None
        else:
            for s in self._sites_cache:
                if s["nom"] == val:
                    self._selected_site_id = s["id"]
                    break
        self._fetch_data()

    # ── Navigation par date ───────────────────────────────────────────
    def _prev_day(self):
        self._date -= timedelta(days=1)
        self._update_date_label()
        self._fetch_data()

    def _next_day(self):
        if self._date < datetime.now().date():
            self._date += timedelta(days=1)
            self._update_date_label()
            self._fetch_data()

    def _go_today(self):
        self._date = datetime.now().date()
        self._update_date_label()
        self._fetch_data()

    def _update_date_label(self):
        today = datetime.now().date()
        if self._date == today:
            txt = "Aujourd'hui"
        elif self._date == today - timedelta(days=1):
            txt = "Hier"
        else:
            txt = self._date.strftime("%d/%m/%Y")
        self.date_label.config(text=txt)

    # ── Chargement des données ────────────────────────────────────────
    def _fetch_data(self):
        if self._loading:
            return
        self._loading = True
        self._set_status("Chargement...")

        date_str = self._date.isoformat()
        site_id = self._selected_site_id

        def work():
            return api_client.get_today_pointages(site_id=site_id, date=date_str)

        def on_error(error):
            logging.error(f"Erreur lors de la récupération du journal du jour : {error}")
            self._on_error(error)

        run_async(self.app, work, on_success=self._on_data_loaded, on_error=on_error)

    def _on_data_loaded(self, result):
        self._loading = False
        self._last_refresh = datetime.now()
        self.last_refresh_label.config(
            text=f"Actualisé à {self._last_refresh.strftime('%H:%M:%S')} · auto-refresh 30s")
        self.pointages = result.get("data", [])
        self._render(self.pointages)

    def _on_error(self, error):
        self._loading = False
        message = getattr(error, "message", str(error))
        self._set_status(message, error=True)

    def _set_status(self, msg, error=False):
        for w in self.list_frame.winfo_children():
            w.destroy()
        tk.Label(self.list_frame, text=msg, bg=COLORS["bg"],
                 fg=COLORS["error"] if error else COLORS["muted"],
                 font=("Segoe UI", 10), wraplength=340, justify="center").pack(pady=40)

    # ── Rendu de la liste ─────────────────────────────────────────────
    def _render(self, items):
        for w in self.list_frame.winfo_children():
            w.destroy()

        # Compteurs
        nb_total = len(items)
        nb_presents = sum(1 for p in items if p.get("heure_arrivee") and not p.get("heure_depart"))
        nb_partis = sum(1 for p in items if p.get("heure_arrivee") and p.get("heure_depart"))
        self.count_label.config(
            text=f"— {nb_total} entrée{'s' if nb_total != 1 else ''}  ·  {nb_presents} présent{'s' if nb_presents != 1 else ''}  ·  {nb_partis} parti{'s' if nb_partis != 1 else ''}")

        if not items:
            tk.Label(self.list_frame, text="Aucun pointage pour cette journée.",
                     bg=COLORS["bg"], fg=COLORS["muted_light"],
                     font=("Segoe UI", 11)).pack(pady=50)
            return

        for item in items:
            self._render_card(item)

    def _render_card(self, p: dict):
        # ── Déterminer statut de présence ──
        statut_txt, statut_color = fmt_statut_presence(p)

        # ── Couleurs période ───────────────
        periode = p.get("periode", "")
        p_label, p_fg, p_bg = PERIODE_LABEL.get(periode, (periode, COLORS["muted"], COLORS["bg_alt"]))

        # ── Carte ──────────────────────────
        card = tk.Frame(self.list_frame, bg=COLORS["card"], padx=14, pady=10)
        card.pack(fill="x", pady=4)

        # Ligne 1 : Nom Prénom  ·  poste (droite)
        line1 = tk.Frame(card, bg=COLORS["card"])
        line1.pack(fill="x")
        tk.Label(line1, text=p.get("employe_nom", "—"), bg=COLORS["card"], fg=COLORS["dark"],
                 font=("Segoe UI", 12, "bold")).pack(side="left")
        if p.get("employe_poste"):
            tk.Label(line1, text=p["employe_poste"], bg=COLORS["card"], fg=COLORS["muted_light"],
                     font=("Segoe UI", 9)).pack(side="right")

        # Ligne 2 : heure arrivée → départ  ·  badge période  ·  statut
        line2 = tk.Frame(card, bg=COLORS["card"])
        line2.pack(fill="x", pady=(6, 0))

        arrivee = fmt_heure(p.get("heure_arrivee"))
        depart  = fmt_heure(p.get("heure_depart"))
        heure_txt = f"{arrivee}  →  {depart}"
        tk.Label(line2, text=heure_txt, bg=COLORS["card"], fg=COLORS["text"],
                 font=("Segoe UI", 13)).pack(side="left")

        # Badge période
        badge_periode = tk.Label(line2, text=p_label, bg=p_bg, fg=p_fg,
                                  font=("Segoe UI", 8, "bold"), padx=8, pady=2)
        badge_periode.pack(side="left", padx=(12, 0))

        # Badge garde si nuit
        if p.get("type_journee") == "garde":
            tk.Label(line2, text="Garde", bg=COLORS["garde_bg"], fg=COLORS["garde"],
                     font=("Segoe UI", 8, "bold"), padx=8, pady=2).pack(side="left", padx=(4, 0))

        # Statut de présence (droite)
        tk.Label(line2, text=statut_txt, bg=COLORS["card"], fg=statut_color,
                 font=("Segoe UI", 9, "bold")).pack(side="right")

        # Ligne 3 (optionnelle) : site si "tous les sites" + retard
        extra_parts = []
        if not self._selected_site_id and p.get("site"):
            extra_parts.append(f"📍 {p['site']}")
        retard = p.get("retard")
        if retard and retard != "0:00:00":
            parts = retard.split(":")
            mins = int(parts[0]) * 60 + int(parts[1]) if len(parts) >= 2 else 0
            extra_parts.append(f"⚠ {mins} min de retard")

        if extra_parts:
            line3 = tk.Frame(card, bg=COLORS["card"])
            line3.pack(fill="x", pady=(4, 0))
            tk.Label(line3, text="  ·  ".join(extra_parts), bg=COLORS["card"],
                     fg=COLORS["muted_light"], font=("Segoe UI", 8)).pack(side="left")
