# screens/sortie_anticipee_dialog.py
"""
Dialogue de confirmation affiché quand un employé scanne sa sortie
(matin ou après-midi) avant l'heure de fermeture normale du site.

Reproduit côté desktop la logique de services._process_normal_state_machine
côté serveur (status == 'confirm_required', code == 'SORTIE_ANTICIPEE') :
l'agent doit explicitement confirmer que la sortie anticipée est autorisée
avant qu'elle ne soit enregistrée. Chaque employé ne dispose que d'une
autorisation de ce type par mois (voir modèle AutorisationSortie).
"""

import tkinter as tk

from utils import COLORS


class SortieAnticipeeDialog(tk.Toplevel):
    """
    message                  : texte explicatif renvoyé par le serveur
                                (minutes d'anticipation, quota du mois...)
    autorisation_disponible  : bool — True si le quota mensuel n'est pas
                                encore épuisé
    on_confirm / on_cancel   : callbacks sans argument
    """

    def __init__(self, app, message: str, autorisation_disponible: bool,
                 on_confirm, on_cancel):
        super().__init__(app)
        self.title("Sortie anticipée")
        self.configure(bg=COLORS["bg"])
        self.resizable(False, False)
        self.transient(app)
        self.grab_set()
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self._choice_made = False

        icon = "⚠" if autorisation_disponible else "⛔"
        tk.Label(self, text=icon, bg=COLORS["bg"], fg=COLORS["warning"],
                 font=("Segoe UI", 32)).pack(pady=(20, 4))

        tk.Label(self, text=message, bg=COLORS["bg"], fg=COLORS["dark"],
                 font=("Segoe UI", 10), wraplength=340, justify="left").pack(
                     padx=24, pady=(0, 16))

        btn_frame = tk.Frame(self, bg=COLORS["bg"])
        btn_frame.pack(fill="x", padx=20, pady=(0, 20))

        if autorisation_disponible:
            tk.Button(
                btn_frame, text="Confirmer la sortie anticipée",
                bg=COLORS["warning"], fg="white", relief="flat", pady=8,
                command=self._confirm,
            ).pack(fill="x", pady=3)
        else:
            tk.Label(
                btn_frame,
                text="Autorisation mensuelle déjà utilisée : "
                     "cette sortie sera enregistrée comme non autorisée.",
                bg=COLORS["bg"], fg=COLORS["error"], font=("Segoe UI", 8),
                wraplength=320, justify="left",
            ).pack(fill="x", pady=(0, 8))
            tk.Button(
                btn_frame, text="Enregistrer quand même (non autorisée)",
                bg=COLORS["error"], fg="white", relief="flat", pady=8,
                command=self._confirm,
            ).pack(fill="x", pady=3)

        tk.Button(
            btn_frame, text="Annuler", bg="#dddddd", fg=COLORS["dark"],
            relief="flat", pady=8, command=self._cancel,
        ).pack(fill="x", pady=3)

        self.protocol("WM_DELETE_WINDOW", self._cancel)

    def _confirm(self):
        if self._choice_made:
            return
        self._choice_made = True
        self.destroy()
        self.on_confirm()

    def _cancel(self):
        if self._choice_made:
            return
        self._choice_made = True
        self.destroy()
        self.on_cancel()
