# screens/scan.py
"""
Équivalent de mobile/ScanMobileApp/src/screens/ScanScreen.tsx

Deux sources de scan possibles :
  - Webcam : via OpenCV et son détecteur QR intégré (cv2.QRCodeDetector),
    pas de dépendance native supplémentaire (zbar).
  - Scanner USB (douchette) : la quasi-totalité des douchettes USB
    fonctionnent en mode "keyboard wedge" — elles s'enregistrent auprès de
    Windows comme un clavier et "tapent" le contenu du code suivi d'une
    touche Entrée. On capture donc ça via un champ de saisie toujours
    focalisé pendant que ce mode est actif.

La logique métier (mode jour/nuit, vérification de garde en cours, appels
API) reproduit fidèlement le fichier ScanScreen.tsx d'origine, quelle que
soit la source du scan.
"""

import tkinter as tk
from tkinter import messagebox

import cv2
from PIL import Image, ImageTk

import api_client
import storage
from utils import COLORS, run_async


class GardeChoiceDialog(tk.Toplevel):
    """Équivalent de l'Alert à 3 boutons affichée quand une garde est en cours."""

    def __init__(self, app, message, on_choice):
        super().__init__(app)
        self.title("Garde en cours")
        self.configure(bg=COLORS["bg"])
        self.resizable(False, False)
        self.transient(app)
        self.grab_set()
        self.on_choice = on_choice
        self._choice_made = False

        tk.Label(self, text=message, bg=COLORS["bg"], fg=COLORS["dark"], font=("Segoe UI", 10),
                 wraplength=320, justify="left").pack(padx=20, pady=(20, 16))

        btn_frame = tk.Frame(self, bg=COLORS["bg"])
        btn_frame.pack(fill="x", padx=20, pady=(0, 20))

        tk.Button(btn_frame, text="Terminer cette garde", bg=COLORS["primary"], fg="white",
                  relief="flat", pady=8, command=lambda: self._choose("end")).pack(fill="x", pady=3)
        tk.Button(btn_frame, text="Démarrer une nouvelle garde", bg=COLORS["garde"], fg="white",
                  relief="flat", pady=8, command=lambda: self._choose("new")).pack(fill="x", pady=3)
        tk.Button(btn_frame, text="Annuler", bg=COLORS["border"], fg=COLORS["dark"],
                  relief="flat", pady=8, command=lambda: self._choose("cancel")).pack(fill="x", pady=3)

        self.protocol("WM_DELETE_WINDOW", lambda: self._choose("cancel"))

    def _choose(self, choice):
        if self._choice_made:
            return
        self._choice_made = True
        self.destroy()
        self.on_choice(choice)


class ScanScreen(tk.Frame):
    TITLE = "Scanner"

    SCAN_COOLDOWN_SECONDS = 2  # équivalent setTimeout(() => setScanned(false), 2000)
    FRAME_INTERVAL_MS = 33     # ~30 fps
    SOURCE_STORAGE_KEY = "scan_source"  # 'webcam' | 'usb'

    def __init__(self, parent, app):
        super().__init__(parent, bg="black")
        self.app = app
        self.mode = "day"          # 'day' | 'night' — équivalent useState<'day'|'night'>
        self.source = storage.get(self.SOURCE_STORAGE_KEY) or "webcam"  # 'webcam' | 'usb'
        self.scanned = False
        self.loading = False
        self.cap = None
        self.camera_running = False
        self._active = False       # écran actuellement affiché
        self.detector = cv2.QRCodeDetector()
        self._photo_image = None  # garde une référence pour éviter le garbage collector

        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────
    def _build_ui(self):
        top_bar = tk.Frame(self, bg="black")
        top_bar.pack(fill="x")
        back_btn = tk.Button(top_bar, text="← Retour", bg="black", fg="white", relief="flat", bd=0,
                              font=("Segoe UI", 10, "bold"), command=self._on_back, cursor="hand2",
                              activebackground="black", activeforeground="white")
        back_btn.pack(side="left", padx=10, pady=8)

        self.site_info_label = tk.Label(top_bar, text="", bg="black", fg="white",
                                         font=("Segoe UI", 10))
        self.site_info_label.pack(side="left", padx=10)

        # ── Bascule source : Webcam / Scanner USB ───────────────────────
        source_toggle = tk.Frame(top_bar, bg=COLORS["dark"])
        source_toggle.pack(side="right", padx=10, pady=4)
        self.webcam_btn = tk.Button(source_toggle, text="📷 Webcam", relief="flat", bd=0,
                                     padx=10, pady=5, font=("Segoe UI", 9),
                                     command=lambda: self._set_source("webcam"), cursor="hand2")
        self.webcam_btn.pack(side="left", padx=1, pady=1)
        self.usb_btn = tk.Button(source_toggle, text="🔌 Scanner USB", relief="flat", bd=0,
                                  padx=10, pady=5, font=("Segoe UI", 9),
                                  command=lambda: self._set_source("usb"), cursor="hand2")
        self.usb_btn.pack(side="left", padx=1, pady=1)

        # ── Zone centrale : vidéo (webcam) OU panneau de saisie (USB) ───
        self.center_area = tk.Frame(self, bg="black")
        self.center_area.pack(fill="both", expand=True)

        self.video_label = tk.Label(self.center_area, bg="black")

        self.usb_panel = tk.Frame(self.center_area, bg="black")
        tk.Label(self.usb_panel, text="🔌", bg="black", fg="white",
                 font=("Segoe UI", 48)).pack(pady=(60, 10))
        tk.Label(self.usb_panel, text="Scanner USB prêt", bg="black", fg="white",
                 font=("Segoe UI", 14, "bold")).pack()
        tk.Label(self.usb_panel, text="Présentez le badge devant la douchette", bg="black",
                 fg=COLORS["muted_light"], font=("Segoe UI", 10)).pack(pady=(4, 24))
        self.usb_var = tk.StringVar()
        self.usb_entry = tk.Entry(self.usb_panel, textvariable=self.usb_var, justify="center",
                                   font=("Segoe UI", 14), bg=COLORS["dark"], fg="white",
                                   insertbackground="white", relief="flat", width=30)
        self.usb_entry.pack(ipady=8)
        self.usb_entry.bind("<Return>", self._on_usb_enter)
        tk.Label(self.usb_panel, text="(la saisie manuelle + Entrée fonctionne aussi, pour tester)",
                 bg="black", fg=COLORS["muted"], font=("Segoe UI", 8)).pack(pady=(10, 0))

        self.hint_label = tk.Label(self, text="Placez le QR code dans le cadre", bg="black",
                                    fg=COLORS["muted_light"], font=("Segoe UI", 10))
        self.hint_label.pack(pady=(0, 6))

        bottom = tk.Frame(self, bg="black")
        bottom.pack(pady=(0, 18))

        mode_toggle = tk.Frame(bottom, bg=COLORS["dark"])
        mode_toggle.pack()
        self.day_btn = tk.Button(mode_toggle, text="☀ Jour", relief="flat", bd=0, padx=18, pady=8,
                                  command=lambda: self._set_mode("day"), cursor="hand2")
        self.day_btn.pack(side="left", padx=2, pady=2)
        self.night_btn = tk.Button(mode_toggle, text="🌙 Nuit", relief="flat", bd=0, padx=18, pady=8,
                                    command=lambda: self._set_mode("night"), cursor="hand2")
        self.night_btn.pack(side="left", padx=2, pady=2)
        self._refresh_mode_buttons()

        self.rescan_btn = tk.Button(bottom, text="⟳ Scanner à nouveau", bg=COLORS["dark"], fg="white",
                                     relief="flat", padx=16, pady=8, command=self._manual_rescan,
                                     cursor="hand2")
        # Affiché seulement après un scan (comme côté mobile)

        self._refresh_source_buttons()

    def _refresh_mode_buttons(self):
        if self.mode == "day":
            self.day_btn.config(bg="white", fg=COLORS["dark"])
            self.night_btn.config(bg=COLORS["dark"], fg=COLORS["muted_light"])
        else:
            # Nuit : accent ambre distinctif, comme sur la page web (periode_nuit:checked)
            self.night_btn.config(bg=COLORS["warning"], fg="white")
            self.day_btn.config(bg=COLORS["dark"], fg=COLORS["muted_light"])

    def _set_mode(self, mode):
        self.mode = mode
        self._refresh_mode_buttons()

    def _refresh_source_buttons(self):
        if self.source == "webcam":
            self.webcam_btn.config(bg="white", fg=COLORS["dark"])
            self.usb_btn.config(bg=COLORS["dark"], fg=COLORS["muted_light"])
        else:
            self.usb_btn.config(bg="white", fg=COLORS["dark"])
            self.webcam_btn.config(bg=COLORS["dark"], fg=COLORS["muted_light"])

    def _set_source(self, source):
        if source == self.source:
            return
        self.source = source
        storage.set(self.SOURCE_STORAGE_KEY, source)
        self._refresh_source_buttons()
        self._activate_source()

    def _activate_source(self):
        """Affiche le bon panneau (vidéo ou USB) et démarre/arrête la caméra en conséquence."""
        if self.source == "webcam":
            self.usb_panel.pack_forget()
            self.video_label.pack(fill="both", expand=True)
            self.hint_label.config(text="Placez le QR code dans le cadre")
            if self._active:
                self.start_camera()
        else:
            self.video_label.pack_forget()
            self.stop_camera()
            self.usb_panel.pack(fill="both", expand=True)
            self.hint_label.config(text="En attente d'un scan (douchette USB)")
            if self._active:
                self._focus_usb_entry()

    def _on_back(self):
        self._active = False
        self.stop_camera()
        self.app.go_back()

    # ── Cycle de vie écran ────────────────────────────────────────────
    def on_enter(self, **params):
        site = self.app.selected_site
        self.site_info_label.config(text=f"📍 {site['nom']}" if site else "")
        self.scanned = False
        self.loading = False
        self.rescan_btn.pack_forget()
        self._active = True
        self._activate_source()

    # ── Source : webcam ──────────────────────────────────────────────
    def start_camera(self):
        if self.camera_running:
            return
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            self.after(0, lambda: messagebox.showerror(
                "Caméra",
                "Impossible d'accéder à la caméra.\n"
                "Vérifiez qu'aucune autre application ne l'utilise, "
                "ou basculez sur « Scanner USB » si vous utilisez une douchette."))
            return
        self.camera_running = True
        self._update_frame()

    def stop_camera(self):
        self.camera_running = False
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    def _update_frame(self):
        if not self.camera_running or self.cap is None:
            return
        ok, frame = self.cap.read()
        if ok:
            frame = cv2.flip(frame, 1)
            self._draw_frame_to_label(frame)

            if not self.scanned and not self.loading:
                data, points, _ = self.detector.detectAndDecode(frame)
                if data:
                    self._on_qr_detected(data)

        self.after(self.FRAME_INTERVAL_MS, self._update_frame)

    def _draw_frame_to_label(self, frame_bgr):
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(rgb)

        # Redimensionner pour remplir le label en conservant le ratio
        label_w = self.video_label.winfo_width() or 400
        label_h = self.video_label.winfo_height() or 500
        img_ratio = img.width / img.height
        target_ratio = label_w / label_h
        if img_ratio > target_ratio:
            new_h = label_h
            new_w = int(new_h * img_ratio)
        else:
            new_w = label_w
            new_h = int(new_w / img_ratio)
        if new_w > 0 and new_h > 0:
            img = img.resize((new_w, new_h))

        self._photo_image = ImageTk.PhotoImage(image=img)
        self.video_label.configure(image=self._photo_image)

    # ── Source : scanner USB (douchette en mode clavier) ────────────────
    def _focus_usb_entry(self):
        if not self._active or self.source != "usb":
            return
        if not self.scanned and not self.loading:
            try:
                self.usb_entry.focus_set()
            except tk.TclError:
                pass
        # Se reprogramme pour reprendre le focus si l'utilisateur clique ailleurs
        self.after(400, self._focus_usb_entry)

    def _on_usb_enter(self, event=None):
        code = self.usb_var.get().strip()
        self.usb_var.set("")
        if not code:
            return
        self._on_qr_detected(code)

    # ── Logique de scan (reproduit handleBarcodeScanned) ────────────────
    def _on_qr_detected(self, data):
        if self.scanned or self.loading:
            return
        if not self.app.selected_site:
            messagebox.showerror("Erreur", "Aucun site sélectionné")
            return

        self.scanned = True
        self.loading = True
        self.hint_label.config(text="Code détecté, vérification...")

        employee_qr = data
        site_id = self.app.selected_site["id"]
        current_mode = self.mode

        if current_mode == "day":
            self._record_scan(employee_qr, site_id, current_mode, force_new=False)
            return

        # Mode nuit -> vérifier d'abord l'état de la garde
        def work():
            return api_client.check_first_scan(employee_qr, site_id)

        def on_success(check_data):
            garde_en_cours = check_data.get("garde_en_cours")
            details = check_data.get("garde_en_cours_details")

            if garde_en_cours:
                message = "Une garde est déjà en cours."
                if details:
                    date = details.get("date_pointage", "date inconnue")
                    heure_raw = details.get("heure_arrivee", "")
                    heure = heure_raw[:5] if heure_raw else "heure inconnue"
                    site_nom = (details.get("site") or {}).get("nom", "site inconnu")
                    message = (f"Une garde a commencé le {date} à {heure} sur {site_nom}.\n"
                               "Que souhaitez-vous faire ?")

                def on_choice(choice):
                    if choice == "end":
                        self._record_scan(employee_qr, site_id, current_mode, force_new=False)
                    elif choice == "new":
                        self._record_scan(employee_qr, site_id, current_mode, force_new=True)
                    else:
                        self._reset_scan_state()

                GardeChoiceDialog(self.app, message, on_choice)
            else:
                self._record_scan(employee_qr, site_id, current_mode, force_new=False)

        def on_error(error):
            message = getattr(error, "message", str(error))
            messagebox.showerror("Erreur", message or "Impossible de vérifier l'état des gardes")
            self._reset_scan_state()

        run_async(self.app, work, on_success=on_success, on_error=on_error)

    def _record_scan(self, employee_qr, site_id, current_mode, force_new=False):
        def work():
            return api_client.record_scan(
                employee_qr, site_id, current_mode,
                force_new=force_new,
            )

        def on_success(result):
            data = result["data"]

            if result["ok"]:
                messagebox.showinfo("Succès", data.get("message", "Pointage enregistré"))
            else:
                messagebox.showerror("Erreur", data.get("message", "Erreur serveur"))
            self._finish_scan_cycle()

        def on_error(error):
            message = getattr(error, "message", str(error))
            messagebox.showerror("Erreur réseau", message or "Impossible de contacter le serveur")
            self._finish_scan_cycle()

        run_async(self.app, work, on_success=on_success, on_error=on_error)

    def _reset_scan_state(self):
        self.loading = False
        self.scanned = False
        self._update_hint()
        if self.source == "usb":
            self._focus_usb_entry()

    def _finish_scan_cycle(self):
        self.loading = False
        self.rescan_btn.pack(pady=(0, 0))
        self.after(self.SCAN_COOLDOWN_SECONDS * 1000, self._auto_clear_scanned)

    def _auto_clear_scanned(self):
        self.scanned = False
        self._update_hint()
        self.rescan_btn.pack_forget()
        if self.source == "usb":
            self._focus_usb_entry()

    def _manual_rescan(self):
        self.scanned = False
        self._update_hint()
        self.rescan_btn.pack_forget()
        if self.source == "usb":
            self._focus_usb_entry()

    def _update_hint(self):
        if self.source == "usb":
            self.hint_label.config(text="En attente d'un scan (douchette USB)")
        else:
            self.hint_label.config(text="Placez le QR code dans le cadre")
