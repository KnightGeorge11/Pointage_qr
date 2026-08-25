# screens/login.py
"""Équivalent de mobile/ScanMobileApp/src/screens/LoginScreen.tsx"""

import tkinter as tk

import api_client
from utils import COLORS, run_async


class LoginScreen(tk.Frame):
    TITLE = "Connexion"

    def __init__(self, parent, app):
        super().__init__(parent, bg=COLORS["bg"])
        self.app = app
        self._build_ui()

    def _build_ui(self):
        card = tk.Frame(self, bg=COLORS["card"], padx=28, pady=28)
        card.place(relx=0.5, rely=0.42, anchor="center", width=340)

        tk.Label(card, text="Pointage QR", bg=COLORS["card"], fg=COLORS["dark"],
                 font=("Segoe UI", 20, "bold")).pack()
        tk.Label(card, text="Connexion opérateur", bg=COLORS["card"], fg=COLORS["muted"],
                 font=("Segoe UI", 10)).pack(pady=(2, 20))

        self.error_label = tk.Label(card, text="", bg=COLORS["error_dim"], fg=COLORS["error_text"],
                                     font=("Segoe UI", 9), wraplength=280, justify="left")

        tk.Label(card, text="Identifiant", bg=COLORS["card"], fg=COLORS["muted"],
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(4, 4))
        self.username_var = tk.StringVar()
        username_entry = tk.Entry(card, textvariable=self.username_var, font=("Segoe UI", 11))
        username_entry.pack(fill="x")

        tk.Label(card, text="Mot de passe", bg=COLORS["card"], fg=COLORS["muted"],
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(12, 4))
        self.password_var = tk.StringVar()
        password_entry = tk.Entry(card, textvariable=self.password_var, font=("Segoe UI", 11), show="•")
        password_entry.pack(fill="x")
        password_entry.bind("<Return>", lambda e: self._login())

        self.login_btn = tk.Button(card, text="Se connecter", command=self._login,
                                    bg=COLORS["primary"], fg="white", relief="flat",
                                    font=("Segoe UI", 11, "bold"), pady=10)
        self.login_btn.pack(fill="x", pady=(24, 0))

        tk.Label(card, text="Utilisez votre compte utilisateur habituel — ce compte identifie\n"
                             "uniquement l'opérateur de l'application, pas les employés scannés.",
                 bg=COLORS["card"], fg=COLORS["muted"], font=("Segoe UI", 8),
                 justify="center").pack(pady=(20, 0))

    def on_enter(self, **params):
        self.password_var.set("")
        self.error_label.pack_forget()

    def _login(self):
        username = self.username_var.get().strip()
        password = self.password_var.get()
        if not username or not password:
            self._show_error("Identifiant et mot de passe requis.")
            return

        self.login_btn.config(state="disabled", text="Connexion...")
        self.error_label.pack_forget()

        def on_success(user):
            self.login_btn.config(state="normal", text="Se connecter")
            self.password_var.set("")
            self.app.on_login_success(user)

        def on_error(err):
            self.login_btn.config(state="normal", text="Se connecter")
            self._show_error(str(err))

        run_async(self.app, lambda: api_client.login(username, password),
                  on_success=on_success, on_error=on_error)

    def _show_error(self, message: str):
        self.error_label.config(text=message)
        self.error_label.pack(fill="x", pady=(0, 12), before=self.login_btn)
