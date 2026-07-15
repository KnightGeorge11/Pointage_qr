# screens/site_selection.py
"""Équivalent de mobile/ScanMobileApp/src/screens/SiteSelectionScreen.tsx"""

import tkinter as tk
from tkinter import messagebox

import api_client
from utils import COLORS, run_async


class SiteSelectionScreen(tk.Frame):
    TITLE = "Sélection du site"

    def __init__(self, parent, app):
        super().__init__(parent, bg=COLORS["bg"])
        self.app = app
        self.sites = []
        self._build_ui()

    def _build_ui(self):
        header = tk.Frame(self, bg=COLORS["bg"])
        header.pack(fill="x", padx=16, pady=(16, 8))

        back_btn = tk.Button(header, text="← Retour", bg=COLORS["bg"], fg=COLORS["primary"],
                              relief="flat", bd=0, font=("Segoe UI", 10, "bold"),
                              command=self.app.go_back, cursor="hand2")
        back_btn.pack(side="left")

        title = tk.Label(header, text="Sélection du site", bg=COLORS["bg"], fg=COLORS["dark"],
                          font=("Segoe UI", 16, "bold"))
        title.pack(side="left", padx=(14, 0))

        refresh_btn = tk.Button(header, text="⟳", bg=COLORS["bg"], fg=COLORS["primary"],
                                 relief="flat", bd=0, font=("Segoe UI", 13, "bold"),
                                 command=lambda: self._load_sites(force_refresh=True), cursor="hand2")
        refresh_btn.pack(side="right")

        self.status_label = tk.Label(self, text="Connexion au serveur...", bg=COLORS["bg"],
                                      fg=COLORS["muted"], font=("Segoe UI", 10))
        self.status_label.pack(pady=4)

        # Zone scrollable pour la liste de sites
        canvas_frame = tk.Frame(self, bg=COLORS["bg"])
        canvas_frame.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        self.canvas = tk.Canvas(canvas_frame, bg=COLORS["bg"], highlightthickness=0)
        scrollbar = tk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
        self.list_frame = tk.Frame(self.canvas, bg=COLORS["bg"])

        self.list_frame.bind("<Configure>",
                              lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.list_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def on_enter(self, **params):
        self._load_sites()

    def _load_sites(self, force_refresh=False):
        self.status_label.config(text="Chargement des sites...")
        for widget in self.list_frame.winfo_children():
            widget.destroy()

        def work():
            return api_client.sync_sites() if force_refresh else api_client.get_sites()

        run_async(self.app, work, on_success=self._render_sites, on_error=self._on_load_error)

    def _on_load_error(self, error):
        message = getattr(error, "message", str(error))
        self.status_label.config(text=f"Erreur : {message}", fg=COLORS["error"])

    def _render_sites(self, sites):
        self.sites = sites
        self.status_label.config(text=f"{len(sites)} site(s) disponible(s)", fg=COLORS["muted"])
        selected_id = self.app.selected_site["id"] if self.app.selected_site else None

        if not sites:
            tk.Label(self.list_frame, text="Aucun site disponible.", bg=COLORS["bg"],
                     fg=COLORS["muted"]).pack(pady=20)
            return

        for site in sites:
            is_selected = site["id"] == selected_id
            item_bg = COLORS["primary_dim"] if is_selected else COLORS["card"]
            item = tk.Frame(self.list_frame, bg=item_bg, padx=16, pady=14, cursor="hand2")
            item.pack(fill="x", pady=4)

            icon = tk.Label(item, text="📍", bg=item_bg, font=("Segoe UI", 14))
            icon.pack(side="left")

            text_frame = tk.Frame(item, bg=item_bg)
            text_frame.pack(side="left", fill="x", expand=True, padx=(14, 0))
            tk.Label(text_frame, text=site["nom"], bg=item_bg, fg=COLORS["dark"],
                     font=("Segoe UI", 12, "bold"), anchor="w").pack(anchor="w")
            if site.get("adresse"):
                tk.Label(text_frame, text=site["adresse"], bg=item_bg, fg=COLORS["muted"],
                         font=("Segoe UI", 9), anchor="w").pack(anchor="w")

            if is_selected:
                tk.Label(item, text="✓", bg=item_bg, fg=COLORS["primary"],
                         font=("Segoe UI", 14, "bold")).pack(side="right")

            clickable = [item, icon, text_frame] + list(text_frame.winfo_children())
            for w in clickable:
                w.bind("<Button-1>", lambda e, s=site: self._select_site(s))

    def _select_site(self, site):
        api_client.save_selected_site(site)
        self.app.set_selected_site(site)
        if messagebox.askyesno("Succès", f"Site « {site['nom']} » sélectionné.\n\nLancer le scanner ?"):
            self.app.navigate("ScanScreen")
        else:
            self._render_sites(self.sites)
