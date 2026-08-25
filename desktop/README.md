# Pointage QR — Application Desktop (Python)

Application de bureau qui reproduit fidèlement les fonctionnalités de
l'application mobile `ScanMobileApp` (React Native), pour permettre le
pointage par QR code depuis un PC équipé d'une webcam (utile pour un poste
fixe à l'accueil d'un site, par exemple).

## Fonctionnalités (identiques au mobile)

- **Accueil** : statut de connexion à l'API (point vert/rouge), site
  sélectionné, horloge en direct, accès rapide au scan et à l'historique.
- **Sélection du site** : liste des sites récupérés depuis l'API Django
  (`/api/mobile/sites/`), avec mise en cache 5 minutes comme côté mobile.
- **Scanner** : lecture de QR code via la webcam (détecteur QR intégré
  d'OpenCV, aucune dépendance native supplémentaire type `zbar`), bascule
  Jour / Nuit, gestion de la logique de garde (détection d'une garde en
  cours, choix "Terminer / Démarrer une nouvelle / Annuler").
- **Historique** : saisie du matricule, filtres par date (Aujourd'hui /
  Semaine / Mois / Tout) et par période (Tous / Matin / Après-midi / Nuit),
  affichage des heures d'arrivée/départ, durée travaillée, retard.
- **Paramètres serveur** (bonus desktop) : un petit écran accessible depuis
  l'accueil permet de changer l'URL de l'API sans reconstruire l'exécutable
  — utile puisque l'IP de la VM change selon le bail DHCP.

## Structure du projet

```
pointage_qr_desktop/
├── main.py                  # point d'entrée
├── app.py                   # fenêtre principale + navigation entre écrans
├── api_client.py            # client HTTP, miroir de mobile/src/services/api.ts
├── storage.py                # stockage local persistant (équiv. AsyncStorage)
├── utils.py                  # couleurs, helper de thread non-bloquant
├── screens/
│   ├── home.py                # équiv. HomeScreen.tsx
│   ├── site_selection.py      # équiv. SiteSelectionScreen.tsx
│   ├── scan.py                 # équiv. ScanScreen.tsx
│   ├── history.py              # équiv. HistoryScreen.tsx
│   └── settings_dialog.py      # bonus desktop : config URL serveur
├── requirements.txt
└── build_exe.bat             # script de génération de l'exécutable Windows
```

## Installation (développement)

```bash
pip install -r requirements.txt
python main.py
```

Au premier lancement, l'application essaiera de contacter l'API à l'adresse
par défaut `http://pointageqr.local:8000`. Si le serveur n'est pas encore
configuré pour être joignable via ce nom (voir `NETWORK_SETUP.md` à la racine
du projet), ou si vous préférez utiliser l'IP directement, ouvrez
**⚙ Paramètres serveur** depuis l'écran d'accueil pour la modifier (elle est
ensuite mémorisée localement, pas besoin de reconstruire l'exécutable).

## Construire l'exécutable Windows (.exe)

> Important : un `.exe` Windows doit être construit **sur une machine
> Windows** (PyInstaller ne fait pas de cross-compilation fiable depuis
> Linux). Le script ci-dessous a été testé et validé dans ce projet (la
> construction réussit et l'exécutable démarre correctement) ; il vous
> suffit de l'exécuter sur votre PC Windows 10.

1. Installez Python 3.11+ sur la machine Windows (cochez "Add to PATH").
2. Copiez le dossier `pointage_qr_desktop` sur cette machine.
3. Double-cliquez sur `build_exe.bat` (ou exécutez-le depuis un terminal).
4. L'exécutable final sera généré dans `dist\PointageQR.exe`.

Le script effectue automatiquement :
```bat
pip install -r requirements.txt
pyinstaller --noconfirm --onefile --windowed --name PointageQR --collect-all cv2 main.py
```

`PointageQR.exe` est un fichier unique, autonome (aucune installation de
Python n'est requise sur le poste final).

## Notes techniques

- **Détection QR** : utilise `cv2.QRCodeDetector()` plutôt que `pyzbar`,
  car cela évite la dépendance native `libzbar` qui complique souvent
  l'empaquetage Windows. Le format de QR attendu reste identique à celui
  du serveur Django : `EMPLOYE:matricule:token`.
- **Logique métier de scan** (mode jour/nuit, gestion garde en cours,
  cooldown anti-double-scan de 2 secondes) reproduit exactement le
  comportement de `ScanScreen.tsx`, jusqu'aux libellés des messages.
- **Endpoints utilisés** (identiques au mobile) :
  - `GET  /api/mobile/test/`
  - `GET  /api/mobile/sites/`
  - `POST /api/mobile/scan/check-first/`
  - `POST /api/mobile/scan/record/`
  - `GET  /api/mobile/pointages/?matricule=...`
- **Stockage local** : `~/.pointage_qr_desktop/settings.json` (équivalent
  desktop d'AsyncStorage) contient l'URL serveur, le site sélectionné, le
  matricule mémorisé et le cache des sites.
- Si une erreur de caméra apparaît ("Impossible d'accéder à la caméra"),
  vérifiez qu'aucune autre application (Teams, Zoom, etc.) ne l'utilise
  déjà, et que les pilotes webcam sont à jour.
