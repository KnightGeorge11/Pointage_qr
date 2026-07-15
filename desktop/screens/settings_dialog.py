# screens/settings_dialog.py
"""
Petite boîte de dialogue pour configurer l'URL de l'API.
Nécessaire en pratique car l'IP du serveur (VM locale) change selon
l'attribution DHCP — non présent dans le mobile (codé en dur) mais
indispensable côté desktop pour ne pas avoir à reconstruire l'app
à chaque changement d'IP.
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
        self.geometry("360x220")
        self.resizable(False, False)
        self.configure(bg=COLORS["bg"])
        self.transient(app)
        self.grab_set()

        tk.Label(self, text="URL de l'API", bg=COLORS["bg"], fg=COLORS["dark"],
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=20, pady=(20, 6))

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

    def _test(self):
        url = self.url_var.get().strip()
        if not url:
            return
        previous = api_client.get_base_url()
        api_client.set_base_url(url)
        self.result_label.config(text="Test en cours...", fg=COLORS["muted"])

        def restore_and_report(result):
            api_client.set_base_url(previous)  # ne pas sauvegarder tant que non confirmé
            if result["success"]:
                self.result_label.config(text="Connexion réussie ✅", fg=COLORS["success"])
            else:
                self.result_label.config(text=f"Échec : {result['message']}", fg=COLORS["error"])

        run_async(self.app, api_client.test_connection, on_success=restore_and_report,
                  on_error=lambda e: self.result_label.config(text=f"Erreur : {e}", fg=COLORS["error"]))

    def _save(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror("Erreur", "Veuillez entrer une URL.")
            return
        api_client.set_base_url(url)
        messagebox.showinfo("Succès", "Configuration enregistrée.")
        self.destroy()
