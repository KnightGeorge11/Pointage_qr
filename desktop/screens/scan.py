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

        tk.Label(
            self,
            text=message,
            bg=COLORS["bg"],
            fg=COLORS["dark"],
            font=("Segoe UI", 10),
            wraplength=320,
            justify="left",
        ).pack(padx=20, pady=(20, 16))

        btn_frame = tk.Frame(self, bg=COLORS["bg"])
        btn_frame.pack(fill="x", padx=20, pady=(0, 20))

        tk.Button(
            btn_frame,
            text="Terminer cette garde",
            bg=COLORS["primary"],
            fg="white",
            relief="flat",
            pady=8,
            command=lambda: self._choose("end"),
        ).pack(fill="x", pady=3)

        tk.Button(
            btn_frame,
            text="Démarrer une nouvelle garde",
            bg=COLORS["garde"],
            fg="white",
            relief="flat",
            pady=8,
            command=lambda: self._choose("new"),
        ).pack(fill="x", pady=3)

        tk.Button(
            btn_frame,
            text="Annuler",
            bg=COLORS["border"],
            fg=COLORS["dark"],
            relief="flat",
            pady=8,
            command=lambda: self._choose("cancel"),
        ).pack(fill="x", pady=3)

        self.protocol(
            "WM_DELETE_WINDOW",
            lambda: self._choose("cancel"),
        )

    def _choose(self, choice):
        if self._choice_made:
            return

        self._choice_made = True
        self.destroy()
        self.on_choice(choice)


class ScanScreen(tk.Frame):
    TITLE = "Scanner"

    SCAN_COOLDOWN_SECONDS = 2
    FRAME_INTERVAL_MS = 33
    SOURCE_STORAGE_KEY = "scan_source"

    def __init__(self, parent, app):
        super().__init__(parent, bg="black")

        self.app = app

        self.mode = "day"
        self.source = storage.get(self.SOURCE_STORAGE_KEY) or "webcam"

        self.scanned = False
        self.loading = False

        self.cap = None
        self.camera_running = False
        self._active = False

        self.detector = cv2.QRCodeDetector()
        self._photo_image = None

        self._build_ui()

    # ================================================================
    # UI
    # ================================================================

    def _build_ui(self):
        """
        Construit l'interface de manière adaptative.
        """

        # ============================================================
        # BARRE SUPÉRIEURE
        # ============================================================

        top_bar = tk.Frame(
            self,
            bg="black",
        )

        top_bar.pack(
            side="top",
            fill="x",
        )

        back_btn = tk.Button(
            top_bar,
            text="← Retour",
            bg="black",
            fg="white",
            relief="flat",
            bd=0,
            font=("Segoe UI", 10, "bold"),
            command=self._on_back,
            cursor="hand2",
            activebackground="black",
            activeforeground="white",
        )

        back_btn.pack(
            side="left",
            padx=10,
            pady=8,
        )

        self.site_info_label = tk.Label(
            top_bar,
            text="",
            bg="black",
            fg="white",
            font=("Segoe UI", 10),
        )

        self.site_info_label.pack(
            side="left",
            padx=10,
        )

        # ============================================================
        # SWITCH SOURCE : WEBCAM / USB
        # ============================================================

        source_toggle = tk.Frame(
            top_bar,
            bg=COLORS["dark"],
        )

        source_toggle.pack(
            side="right",
            padx=10,
            pady=4,
        )

        self.webcam_btn = tk.Button(
            source_toggle,
            text="📷 Webcam",
            relief="flat",
            bd=0,
            padx=10,
            pady=5,
            font=("Segoe UI", 9),
            command=lambda: self._set_source("webcam"),
            cursor="hand2",
        )

        self.webcam_btn.pack(
            side="left",
            padx=1,
            pady=1,
        )

        self.usb_btn = tk.Button(
            source_toggle,
            text="🔌 Scanner USB",
            relief="flat",
            bd=0,
            padx=10,
            pady=5,
            font=("Segoe UI", 9),
            command=lambda: self._set_source("usb"),
            cursor="hand2",
        )

        self.usb_btn.pack(
            side="left",
            padx=1,
            pady=1,
        )

        # ============================================================
        # ZONE CENTRALE FLEXIBLE (avec limite de hauteur)
        # ============================================================

        # Conteneur pour la zone centrale avec un poids pour qu'elle
        # ne repousse pas les contrôles du bas
        self.center_container = tk.Frame(
            self,
            bg="black",
        )

        self.center_container.pack(
            side="top",
            fill="both",
            expand=True,
        )

        # On donne un poids de 1 au center_container pour qu'il prenne
        # l'espace disponible mais pas plus
        self.center_container.pack_propagate(False)

        # ------------------------------------------------------------
        # Webcam
        # ------------------------------------------------------------

        self.video_label = tk.Label(
            self.center_container,
            bg="black",
        )

        # ------------------------------------------------------------
        # Scanner USB
        # ------------------------------------------------------------

        self.usb_panel = tk.Frame(
            self.center_container,
            bg="black",
        )

        tk.Label(
            self.usb_panel,
            text="🔌",
            bg="black",
            fg="white",
            font=("Segoe UI", 48),
        ).pack(
            pady=(60, 10),
        )

        tk.Label(
            self.usb_panel,
            text="Scanner USB prêt",
            bg="black",
            fg="white",
            font=("Segoe UI", 14, "bold"),
        ).pack()

        tk.Label(
            self.usb_panel,
            text="Présentez le badge devant la douchette",
            bg="black",
            fg=COLORS["muted_light"],
            font=("Segoe UI", 10),
        ).pack(
            pady=(4, 24),
        )

        # ============================================================
        # INDICATION
        # ============================================================

        self.hint_label = tk.Label(
            self,
            text="Placez le QR code dans le cadre",
            bg="black",
            fg=COLORS["muted_light"],
            font=("Segoe UI", 10),
        )

        self.hint_label.pack(
            side="top",
            fill="x",
            pady=(0, 6),
        )

        # ============================================================
        # CONTROLES DU BAS (toujours visible)
        # ============================================================

        self.bottom_controls = tk.Frame(
            self,
            bg="black",
            height=120,  # Hauteur fixe pour les contrôles du bas
        )

        self.bottom_controls.pack(
            side="bottom",
            fill="x",
            pady=(0, 6),
        )

        # On empêche le redimensionnement du bottom_controls
        self.bottom_controls.pack_propagate(False)

        # ------------------------------------------------------------
        # SWITCH JOUR / NUIT
        # ------------------------------------------------------------

        mode_toggle = tk.Frame(
            self.bottom_controls,
            bg="black",
        )

        mode_toggle.pack(
            pady=(4, 4),
        )

        self.day_btn = tk.Button(
            mode_toggle,
            text="☀️ JOUR",
            bg="white",
            fg=COLORS["dark"],
            activebackground="white",
            activeforeground=COLORS["dark"],
            relief="flat",
            bd=0,
            padx=20,
            pady=8,
            font=("Segoe UI", 10, "bold"),
            command=lambda: self._set_mode("day"),
            cursor="hand2",
        )

        self.day_btn.pack(
            side="left",
            padx=2,
        )

        self.night_btn = tk.Button(
            mode_toggle,
            text="🌙 NUIT",
            bg=COLORS["dark"],
            fg=COLORS["muted_light"],
            activebackground=COLORS["dark"],
            activeforeground="white",
            relief="flat",
            bd=0,
            padx=20,
            pady=8,
            font=("Segoe UI", 10, "bold"),
            command=lambda: self._set_mode("night"),
            cursor="hand2",
        )

        self.night_btn.pack(
            side="left",
            padx=2,
        )

        self._refresh_mode_buttons()

        # ------------------------------------------------------------
        # BOUTON RESCAN
        # ------------------------------------------------------------

        self.rescan_btn = tk.Button(
            self.bottom_controls,
            text="⟳ Scanner à nouveau",
            bg=COLORS["primary"],
            fg="white",
            relief="flat",
            padx=20,
            pady=6,
            font=("Segoe UI", 9, "bold"),
            command=self._manual_rescan,
            cursor="hand2",
        )

        # Le bouton est affiché uniquement après un scan.

        self._refresh_source_buttons()

    # ================================================================
    # MODE JOUR / NUIT
    # ================================================================

    def _refresh_mode_buttons(self):
        if self.mode == "day":
            self.day_btn.config(
                bg="white",
                fg=COLORS["dark"],
            )

            self.night_btn.config(
                bg=COLORS["dark"],
                fg=COLORS["muted_light"],
            )

        else:
            self.night_btn.config(
                bg=COLORS["warning"],
                fg="white",
            )

            self.day_btn.config(
                bg=COLORS["dark"],
                fg=COLORS["muted_light"],
            )

    def _set_mode(self, mode):
        self.mode = mode
        self._refresh_mode_buttons()

    # ================================================================
    # SOURCE WEBCAM / USB
    # ================================================================

    def _refresh_source_buttons(self):
        if self.source == "webcam":
            self.webcam_btn.config(
                bg="white",
                fg=COLORS["dark"],
            )

            self.usb_btn.config(
                bg=COLORS["dark"],
                fg=COLORS["muted_light"],
            )

        else:
            self.usb_btn.config(
                bg="white",
                fg=COLORS["dark"],
            )

            self.webcam_btn.config(
                bg=COLORS["dark"],
                fg=COLORS["muted_light"],
            )

    def _set_source(self, source):
        if source == self.source:
            return

        self.source = source

        storage.set(
            self.SOURCE_STORAGE_KEY,
            source,
        )

        self._refresh_source_buttons()
        self._activate_source()

    def _activate_source(self):
        """
        Affiche le bon panneau :

        - Webcam : vidéo
        - USB : panneau de saisie

        Le mode Jour/Nuit reste indépendant de la source.
        """

        if self.source == "webcam":
            self.usb_panel.pack_forget()

            self.video_label.pack(
                fill="both",
                expand=True,
            )

            self.hint_label.config(
                text="📷 Placez le QR code dans le cadre",
            )

            if self._active:
                self.start_camera()

        else:
            self.video_label.pack_forget()

            self.stop_camera()

            self.usb_panel.pack(
                fill="both",
                expand=True,
            )

            self.hint_label.config(
                text="🔌 En attente d'un scan (douchette USB)",
            )

            if self._active:
                self._focus_usb_entry()

    # ================================================================
    # NAVIGATION
    # ================================================================

    def _on_back(self):
        self._active = False

        self.stop_camera()

        self.app.go_back()

    # ================================================================
    # CYCLE DE VIE
    # ================================================================

    def on_enter(self, **params):
        site = self.app.selected_site

        self.site_info_label.config(
            text=f"📍 {site['nom']}" if site else "",
        )

        self.scanned = False
        self.loading = False

        self.rescan_btn.pack_forget()

        self._active = True

        self._activate_source()

    # ================================================================
    # WEBCAM
    # ================================================================

    def start_camera(self):
        if self.camera_running:
            return

        self.cap = cv2.VideoCapture(0)

        if not self.cap.isOpened():
            self.after(
                0,
                lambda: messagebox.showerror(
                    "Caméra",
                    "Impossible d'accéder à la caméra.\n"
                    "Vérifiez qu'aucune autre application ne l'utilise, "
                    "ou basculez sur « Scanner USB » si vous utilisez une douchette.",
                ),
            )

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

        self.after(
            self.FRAME_INTERVAL_MS,
            self._update_frame,
        )

    def _draw_frame_to_label(self, frame_bgr):
        rgb = cv2.cvtColor(
            frame_bgr,
            cv2.COLOR_BGR2RGB,
        )

        img = Image.fromarray(rgb)

        label_w = self.video_label.winfo_width() or 400
        label_h = self.video_label.winfo_height() or 500

        if label_w <= 1 or label_h <= 1:
            return

        img_ratio = img.width / img.height
        target_ratio = label_w / label_h

        if img_ratio > target_ratio:
            new_h = label_h
            new_w = int(new_h * img_ratio)

        else:
            new_w = label_w
            new_h = int(new_w / img_ratio)

        if new_w > 0 and new_h > 0:
            img = img.resize(
                (new_w, new_h),
            )

        self._photo_image = ImageTk.PhotoImage(
            image=img,
        )

        self.video_label.configure(
            image=self._photo_image,
        )

    # ================================================================
    # SCANNER USB
    # ================================================================

    def _focus_usb_entry(self):
        # Fonction vide car nous n'avons plus de champ de saisie
        pass

    def _on_usb_enter(self, event=None):
        # Fonction vide car nous n'avons plus de champ de saisie
        pass

    # ================================================================
    # LOGIQUE DE SCAN
    # ================================================================

    def _on_qr_detected(self, data):
        if self.scanned or self.loading:
            return

        if not self.app.selected_site:
            messagebox.showerror(
                "Erreur",
                "Aucun site sélectionné",
            )

            return

        self.scanned = True
        self.loading = True

        self.hint_label.config(
            text="⏳ Code détecté, vérification...",
        )

        employee_qr = data
        site_id = self.app.selected_site["id"]
        current_mode = self.mode

        if current_mode == "day":
            self._record_scan(
                employee_qr,
                site_id,
                current_mode,
                force_new=False,
            )

            return

        # Mode nuit : vérifier d'abord l'état de la garde.

        def work():
            return api_client.check_first_scan(
                employee_qr,
                site_id,
            )

        def on_success(check_data):
            garde_en_cours = check_data.get(
                "garde_en_cours",
            )

            if garde_en_cours:
                message = "Une garde est déjà en cours."

                if isinstance(garde_en_cours, dict):
                    date = garde_en_cours.get(
                        "date_pointage",
                        "date inconnue",
                    )

                    heure_raw = garde_en_cours.get(
                        "heure_arrivee",
                        "",
                    )

                    heure = (
                        heure_raw[:5]
                        if heure_raw
                        else "heure inconnue"
                    )

                    site_nom = (
                        check_data.get("site") or {}
                    ).get(
                        "nom",
                        "site inconnu",
                    )

                    message = (
                        f"Une garde a commencé le {date} "
                        f"à {heure} sur {site_nom}.\n"
                        "Que souhaitez-vous faire ?"
                    )

                def on_choice(choice):
                    if choice == "end":
                        self._record_scan(
                            employee_qr,
                            site_id,
                            current_mode,
                            force_new=False,
                        )

                    elif choice == "new":
                        self._record_scan(
                            employee_qr,
                            site_id,
                            current_mode,
                            force_new=True,
                        )

                    else:
                        self._reset_scan_state()

                GardeChoiceDialog(
                    self.app,
                    message,
                    on_choice,
                )

            else:
                self._record_scan(
                    employee_qr,
                    site_id,
                    current_mode,
                    force_new=False,
                )

        def on_error(error):
            message = getattr(
                error,
                "message",
                str(error),
            )

            messagebox.showerror(
                "Erreur",
                message or "Impossible de vérifier l'état des gardes",
            )

            self._reset_scan_state()

        run_async(
            self.app,
            work,
            on_success=on_success,
            on_error=on_error,
        )

    # ================================================================
    # ENREGISTREMENT DU POINTAGE
    # ================================================================

    def _record_scan(
        self,
        employee_qr,
        site_id,
        current_mode,
        force_new=False,
    ):
        def work():
            return api_client.record_scan(
                employee_qr,
                site_id,
                current_mode,
                force_new=force_new,
            )

        def on_success(result):
            data   = result["data"]
            statut = data.get("status")

            if statut == "success":
                messagebox.showinfo(
                    "✅ Succès",
                    data.get(
                        "message",
                        "Pointage enregistré",
                    ),
                )
            elif statut == "warning":
                # HTTP 200 mais anomalie métier (doublon, hors horaires,
                # pause, journée terminée, ...) : ne jamais l'afficher
                # comme un succès silencieux.
                messagebox.showwarning(
                    "⚠️ À vérifier",
                    data.get(
                        "message",
                        "Le pointage a été traité avec une remarque.",
                    ),
                )
            else:
                messagebox.showerror(
                    "❌ Erreur",
                    data.get(
                        "message",
                        "Erreur serveur",
                    ),
                )

            self._finish_scan_cycle()

        def on_error(error):
            message = getattr(
                error,
                "message",
                str(error),
            )

            messagebox.showerror(
                "⚠️ Erreur réseau",
                message or "Impossible de contacter le serveur",
            )

            self._finish_scan_cycle()

        run_async(
            self.app,
            work,
            on_success=on_success,
            on_error=on_error,
        )

    # ================================================================
    # GESTION DU CYCLE DE SCAN
    # ================================================================

    def _reset_scan_state(self):
        self.loading = False
        self.scanned = False

        self._update_hint()

    def _finish_scan_cycle(self):
        self.loading = False

        self.rescan_btn.pack(
            pady=(4, 0),
        )

        self.after(
            self.SCAN_COOLDOWN_SECONDS * 1000,
            self._auto_clear_scanned,
        )

    def _auto_clear_scanned(self):
        self.scanned = False

        self._update_hint()

        self.rescan_btn.pack_forget()

    def _manual_rescan(self):
        self.scanned = False

        self._update_hint()

        self.rescan_btn.pack_forget()

    def _update_hint(self):
        if self.source == "usb":
            self.hint_label.config(
                text="🔌 En attente d'un scan (douchette USB)",
            )

        else:
            self.hint_label.config(
                text="📷 Placez le QR code dans le cadre",
            )