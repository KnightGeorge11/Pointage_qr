# screens/settings_dialog.py
"""
Boîte de dialogue pour configurer l'URL de l'API et se déconnecter.
Nécessaire en pratique car l'IP du serveur (VM locale) change selon
l'attribution DHCP — non présent dans le mobile (codé en dur) mais
indispensable côté desktop pour ne pas avoir à reconstruire l'app
à chaque changement d'IP.

Le jeton d'authentification n'est plus configuré manuellement ici : il est
obtenu automatiquement par login (LoginScreen) et révoqué par déconnexion.
"""

import tkinter as tk
from tkinter import messagebox

import api_client
from utils import COLORS, run_async


class SettingsDialog(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("Paramètres serveur")
        self.geometry("360x360")
        self.resizable(False, False)
        self.configure(bg=COLORS["bg"])
        self.transient(app)
        self.grab_set()

        current_user = api_client.get_current_user()
        if current_user:
            tk.Label(self, text="Connecté en tant que", bg=COLORS["bg"], fg=COLORS["muted"],
                     font=("Segoe UI", 9)).pack(anchor="w", padx=20, pady=(20, 0))
            nom_affiche = (
                f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()
                or current_user.get('username', '')
            )
            tk.Label(self, text=nom_affiche, bg=COLORS["bg"], fg=COLORS["dark"],
                     font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=20, pady=(0, 16))

        tk.Label(self, text="URL de l'API", bg=COLORS["bg"], fg=COLORS["dark"],
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=20, pady=(0, 6))

        self.url_var = tk.StringVar(value=api_client.get_base_url())
        entry = tk.Entry(self, textvariable=self.url_var, font=("Segoe UI", 11))
        entry.pack(fill="x", padx=20)

        tk.Label(self, text="Exemple : http://pointageqr.local:8000", bg=COLORS["bg"], fg=COLORS["muted"],
                 font=("Segoe UI", 8)).pack(anchor="w", padx=20, pady=(4, 16))

        self.result_label = tk.Label(self, text="", bg=COLORS["bg"], font=("Segoe UI", 9))
        self.result_label.pack(pady=(0, 8))

        btn_frame = tk.Frame(self, bg=COLORS["bg"])
        btn_frame.pack(fill="x", padx=20)

        test_btn = tk.Button(btn_frame, text="Tester", command=self._test, bg=COLORS["success"], fg="white",
                              relief="flat", padx=10, pady=6)
        test_btn.pack(side="left")

        save_btn = tk.Button(btn_frame, text="Enregistrer", command=self._save, bg=COLORS["primary"],
                              fg="white", relief="flat", padx=10, pady=6)
        save_btn.pack(side="right")

        logout_btn = tk.Button(self, text="Se déconnecter", command=self._logout,
                                bg=COLORS["error_text"], fg="white", relief="flat", padx=10, pady=10)
        logout_btn.pack(fill="x", padx=20, pady=(30, 20))

    def _test(self):
        url = self.url_var.get().strip()
        if not url:
            return
        self.result_label.config(text="Test en cours...", fg=COLORS["muted"])

        def report(result):
            if result["success"]:
                self.result_label.config(text="Connexion réussie ✅", fg=COLORS["success"])
            else:
                self.result_label.config(text=f"Échec : {result['message']}", fg=COLORS["error"])

        # Teste l'URL saisie sans jamais la persister ni y faire basculer
        # le reste de l'app : tant que ce n'est pas confirmé par
        # "Enregistrer", les autres écrans (statut API, journal du jour...)
        # continuent d'utiliser l'URL réellement configurée.
        run_async(self.app, lambda: api_client.test_connection(base_url=url), on_success=report,
                  on_error=lambda e: self.result_label.config(text=f"Erreur : {e}", fg=COLORS["error"]))

    def _save(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror("Erreur", "Veuillez entrer une URL.")
            return
        api_client.set_base_url(url)
        messagebox.showinfo("Succès", "Configuration enregistrée.")
        self.destroy()

    def _logout(self):
        if not messagebox.askyesno("Déconnexion", "Voulez-vous vraiment vous déconnecter ?"):
            return

        def on_done(_result=None):
            self.destroy()
            self.app.logout()

        # Révoque le jeton côté serveur ET purge le stockage local (voir
        # api_client.logout) même si le serveur est injoignable.
        run_async(self.app, api_client.logout, on_success=on_done, on_error=lambda e: on_done())
