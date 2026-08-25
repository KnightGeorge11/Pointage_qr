# app.py
"""
Application desktop Pointage QR — réplique fidèle de l'application mobile
(ScanMobileApp) construite avec Django + React Native.

Navigation par pile d'écrans (équivalent de @react-navigation/stack) :
  Home -> SiteSelection -> Scan
       -> History

Lancer avec : python main.py
"""

import tkinter as tk
from tkinter import font as tkfont

import api_client
from utils import COLORS, FONT_FAMILY

from screens.login import LoginScreen
from screens.home import HomeScreen
from screens.site_selection import SiteSelectionScreen
from screens.scan import ScanScreen
from screens.history import HistoryScreen


class PointageApp(tk.Tk):
    """Fenêtre principale + gestionnaire de navigation par pile de frames."""

    def __init__(self):
        super().__init__()
        self.title("Pointage QR")
        self.geometry("420x740")
        self.minsize(380, 640)
        self.configure(bg=COLORS["bg"])

        # Police par défaut (fallback si Segoe UI absente, ex. Linux)
        try:
            default_font = tkfont.nametofont("TkDefaultFont")
            default_font.configure(family=FONT_FAMILY, size=10)
        except tk.TclError:
            pass

        # ── État global (équivalent AppContext.tsx) ─────────────────────
        self.selected_site = api_client.get_selected_site()
        self.api_status = {"connected": True}
        # Le compte connecté (opérateur) reste totalement distinct de
        # l'employé scanné pendant un pointage — cet attribut ne sert
        # qu'à l'affichage et à l'authentification applicative.
        self.current_user = api_client.get_current_user()

        # ── Conteneur des écrans empilés ─────────────────────────────────
        container = tk.Frame(self, bg=COLORS["bg"])
        container.pack(fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)
        self.container = container

        self.frames = {}
        for ScreenClass in (LoginScreen, HomeScreen, SiteSelectionScreen, ScanScreen, HistoryScreen):
            frame = ScreenClass(parent=container, app=self)
            self.frames[ScreenClass.__name__] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.history_stack = []
        # Pas de reconnexion visible si un jeton valide existe déjà en
        # stockage local — on démarre directement sur l'accueil.
        if api_client.is_authenticated():
            self.navigate("HomeScreen")
        else:
            self.navigate("LoginScreen")

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Navigation (équivalent navigation.navigate / goBack) ────────────
    def navigate(self, screen_name: str, push=True, **params):
        frame = self.frames[screen_name]
        if hasattr(frame, "on_enter"):
            frame.on_enter(**params)
        frame.tkraise()
        if push:
            if not self.history_stack or self.history_stack[-1] != screen_name:
                self.history_stack.append(screen_name)
        self.title(f"Pointage QR — {frame.TITLE}")

    def go_back(self):
        if len(self.history_stack) > 1:
            self.history_stack.pop()
            previous = self.history_stack[-1]
            self.navigate(previous, push=False)
        else:
            self.navigate("HomeScreen", push=False)

    # ── Authentification (login/logout par utilisateur) ─────────────────
    def on_login_success(self, user: dict):
        """Appelé par LoginScreen une fois le jeton obtenu et stocké."""
        self.current_user = user
        self.history_stack = []
        self.navigate("HomeScreen")

    def logout(self):
        """Le jeton a déjà été révoqué côté serveur et purgé localement
        par api_client.logout() (appelé par SettingsDialog avant ceci).
        Ici on réinitialise seulement l'état applicatif et on retourne
        à l'écran de connexion."""
        self.current_user = None
        self.history_stack = []
        self.navigate("LoginScreen", push=False)
        self.history_stack = ["LoginScreen"]

    # ── État global partagé entre écrans ─────────────────────────────────
    def set_selected_site(self, site):
        self.selected_site = site
        api_client.save_selected_site(site)
        home = self.frames.get("HomeScreen")
        if home:
            home.refresh_site_display()

    def set_api_status(self, connected: bool):
        self.api_status["connected"] = connected
        home = self.frames.get("HomeScreen")
        if home:
            home.refresh_status_display()

    def _on_close(self):
        scan_frame = self.frames.get("ScanScreen")
        if scan_frame:
            scan_frame.stop_camera()
        self.destroy()


def main():
    app = PointageApp()
    app.mainloop()


if __name__ == "__main__":
    main()
