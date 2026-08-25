# screens/home.py
"""Équivalent de mobile/ScanMobileApp/src/screens/HomeScreen.tsx"""

import tkinter as tk
import datetime

import api_client
from utils import COLORS, run_async

MOIS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
           "août", "septembre", "octobre", "novembre", "décembre"]
JOURS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


def format_date_fr(dt: datetime.datetime) -> str:
    return f"{JOURS_FR[dt.weekday()]} {dt.day} {MOIS_FR[dt.month - 1]}"


class HomeScreen(tk.Frame):
    TITLE = "Accueil"

    def __init__(self, parent, app):
        super().__init__(parent, bg=COLORS["bg"])
        self.app = app
        self._build_ui()
        self._tick_clock()
        self._poll_status()

    # ── UI ────────────────────────────────────────────────────────────
    def _build_ui(self):
        pad = dict(padx=20)

        # En-tête
        header = tk.Label(self, text="Pointage QR", bg=COLORS["bg"], fg=COLORS["dark"],
                           font=("Segoe UI", 22, "bold"))
        header.pack(anchor="w", pady=(24, 16), **pad)

        # Carte statut API
        status_card = tk.Frame(self, bg=COLORS["card"], padx=16, pady=14)
        status_card.pack(fill="x", pady=(0, 12), **pad)
        self.status_dot = tk.Canvas(status_card, width=12, height=12, bg=COLORS["card"],
                                     highlightthickness=0)
        self.status_dot.pack(side="left")
        self.status_circle = self.status_dot.create_oval(1, 1, 11, 11, fill=COLORS["success"], outline="")
        self.status_label = tk.Label(status_card, text="Connecté à l'API", bg=COLORS["card"],
                                      fg=COLORS["muted"], font=("Segoe UI", 10), anchor="w")
        self.status_label.pack(side="left", padx=(10, 0))

        # Carte site sélectionné (cliquable)
        site_card = tk.Frame(self, bg=COLORS["card"], padx=16, pady=14, cursor="hand2")
        site_card.pack(fill="x", pady=(0, 12), **pad)
        site_card.bind("<Button-1>", lambda e: self.app.navigate("SiteSelectionScreen"))

        left_icon = tk.Label(site_card, text="📍", bg=COLORS["card"], font=("Segoe UI", 14))
        left_icon.pack(side="left")
        left_icon.bind("<Button-1>", lambda e: self.app.navigate("SiteSelectionScreen"))

        site_text_frame = tk.Frame(site_card, bg=COLORS["card"])
        site_text_frame.pack(side="left", fill="x", expand=True, padx=(12, 0))
        site_label = tk.Label(site_text_frame, text="SITE ACTUEL", bg=COLORS["card"],
                               fg=COLORS["muted_light"], font=("Segoe UI", 8, "bold"), anchor="w")
        site_label.pack(anchor="w")
        self.site_value = tk.Label(site_text_frame, text="Aucun site sélectionné", bg=COLORS["card"],
                                    fg=COLORS["dark"], font=("Segoe UI", 12, "bold"), anchor="w")
        self.site_value.pack(anchor="w")

        chevron = tk.Label(site_card, text="›", bg=COLORS["card"], fg=COLORS["muted_light"],
                            font=("Segoe UI", 16))
        chevron.pack(side="right")
        for w in (site_card, site_text_frame, site_label, chevron):
            w.bind("<Button-1>", lambda e: self.app.navigate("SiteSelectionScreen"))

        # Carte horloge
        clock_card = tk.Frame(self, bg=COLORS["card"], padx=16, pady=20)
        clock_card.pack(fill="x", pady=(0, 12), **pad)
        self.clock_label = tk.Label(clock_card, text="--:--:--", bg=COLORS["card"], fg=COLORS["dark"],
                                     font=("Segoe UI", 32))
        self.clock_label.pack(anchor="w")
        self.clock_date_label = tk.Label(clock_card, text="", bg=COLORS["card"], fg=COLORS["muted"],
                                          font=("Segoe UI", 10))
        self.clock_date_label.pack(anchor="w", pady=(4, 0))

        # Boutons d'action
        actions = tk.Frame(self, bg=COLORS["bg"])
        actions.pack(fill="x", pady=(8, 0), **pad)
        actions.grid_columnconfigure(0, weight=1)
        actions.grid_columnconfigure(1, weight=1)

        scan_btn = tk.Button(actions, text="📷\nScanner", bg=COLORS["dark"], fg="white",
                              font=("Segoe UI", 11, "bold"), relief="flat", bd=0, pady=26,
                              activebackground=COLORS["muted"], activeforeground="white",
                              command=self._on_scan_press, cursor="hand2")
        scan_btn.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        history_btn = tk.Button(actions, text="📋\nHistorique", bg=COLORS["card"], fg=COLORS["dark"],
                                 font=("Segoe UI", 11, "bold"), relief="flat", bd=0, pady=26,
                                 activebackground=COLORS["bg_alt"], activeforeground=COLORS["dark"],
                                 command=lambda: self.app.navigate("HistoryScreen"), cursor="hand2")
        history_btn.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        # Lien discret vers paramètres (URL serveur)
        settings_link = tk.Label(self, text="⚙ Paramètres serveur", bg=COLORS["bg"], fg=COLORS["muted"],
                                  font=("Segoe UI", 9, "underline"), cursor="hand2")
        settings_link.pack(pady=18)
        settings_link.bind("<Button-1>", lambda e: self._open_settings())

    # ── Comportement ─────────────────────────────────────────────────
    def _on_scan_press(self):
        if not self.app.selected_site:
            self.app.navigate("SiteSelectionScreen")
            return
        self.app.navigate("ScanScreen")

    def _tick_clock(self):
        now = datetime.datetime.now()
        self.clock_label.config(text=now.strftime("%H:%M:%S"))
        self.clock_date_label.config(text=format_date_fr(now))
        self.after(1000, self._tick_clock)

    def _poll_status(self):
        run_async(self.app, api_client.check_status,
                  on_success=lambda r: self.app.set_api_status(r["connected"]),
                  on_error=lambda e: self.app.set_api_status(False))
        self.after(15000, self._poll_status)

    def refresh_site_display(self):
        site = self.app.selected_site
        self.site_value.config(text=site["nom"] if site else "Aucun site sélectionné")

    def refresh_status_display(self):
        connected = self.app.api_status.get("connected")
        color = COLORS["success"] if connected else COLORS["error"]
        text = "Connecté à l'API" if connected else "Déconnecté"
        self.status_dot.itemconfig(self.status_circle, fill=color)
        self.status_label.config(text=text)

    def on_enter(self, **params):
        self.refresh_site_display()
        self.refresh_status_display()

    def _open_settings(self):
        from screens.settings_dialog import SettingsDialog
        SettingsDialog(self.app)
