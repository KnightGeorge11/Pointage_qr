# Configuration réseau — Pointage QR

Ce document explique comment configurer le réseau **une bonne fois pour
toutes** pour le vrai lancement (production/VM), sans plus jamais avoir à
modifier un fichier `.py`, `.ts` ou `.tsx` quand l'IP du serveur change.

## Le problème

Le serveur Django tourne sur une VM dont l'IP est distribuée par DHCP. Elle a
déjà changé plusieurs fois (`192.168.3.115` → `192.168.3.16` →
`192.168.3.101`). Avant cette mise à jour, cette IP était codée en dur à
6 endroits différents (`settings.py`, `storage.py`, `constants.ts`,
`settings_dialog.py`, `ConfigScreen.tsx`, `README.md`), donc chaque
changement d'IP obligeait à modifier et redéployer le code.

## Ce qui a changé dans ce projet

**Le serveur Django (`settings.py`)** lit maintenant `ALLOWED_HOSTS`,
`CORS_ALLOWED_ORIGINS` et `CSRF_TRUSTED_ORIGINS` depuis le fichier `.env`
(variables `DJANGO_ALLOWED_HOSTS` et `CORS_EXTRA_ORIGINS`). **C'est le seul
endroit à modifier côté serveur** quand une IP change — un seul fichier,
jamais de code Python.

**Les apps clientes (desktop et mobile)** avaient déjà, avant cette mise à
jour, un écran de paramètres qui enregistre l'URL du serveur localement
(`⚙ Paramètres serveur` côté desktop, écran de config côté mobile). Ce
n'était pas branché avec le reste — c'est maintenant cohérent avec la
même logique : on ne touche jamais au code, on met à jour l'URL une fois
dans l'app après installation.

## Recommandation : régler le problème à la racine (une seule fois)

Deux approches, combinables :

### Option A — IP fixe (la plus fiable, recommandée en priorité)

Une réservation DHCP est le moyen le plus simple de ne plus jamais revoir
l'IP changer, et elle fonctionne partout (Windows, Android, iOS) sans
dépendance supplémentaire :

1. Récupérez l'adresse MAC de la VM : `ip link show` sur la VM (interface
   réseau principale, souvent `enp0s3` ou `eth0`).
2. Dans l'interface d'administration du routeur, section DHCP / réservation
   d'adresse (« Address Reservation », « Static Lease »…), associez cette
   MAC à une IP fixe (par exemple `192.168.3.101`).
3. Redémarrez le réseau de la VM (`sudo netplan apply` ou reboot) : elle
   recevra désormais toujours la même IP.

Alternative sans routeur configurable : IP statique directement dans
Netplan sur la VM (`/etc/netplan/*.yaml`, clé `addresses:`), à condition
qu'elle soit hors de la plage DHCP du routeur pour éviter les conflits.

### Option B — Nom d'hôte via mDNS (confort supplémentaire, pas suffisant seul)

```bash
sudo apt install avahi-daemon
sudo systemctl enable --now avahi-daemon
```

Le serveur devient joignable via `pointageqr.local` depuis les machines qui
savent résoudre le mDNS (Linux, macOS, et Windows si le service Bonjour est
présent). C'est pratique pour un navigateur ou l'app desktop.

**Limite importante :** la résolution `.local` sur **Android n'est pas
fiable** pour les requêtes HTTP classiques (contrairement à des API de
découverte réseau spécifiques que l'app n'utilise pas). Ne comptez donc pas
uniquement sur `pointageqr.local` pour l'app mobile Android — combinez avec
l'option A, ou entrez directement l'IP fixe dans l'app.

## Ce qu'il reste à faire après avoir choisi une IP fixe (une seule fois)

1. **Serveur** — dans `.env`, mettez à jour `DJANGO_ALLOWED_HOSTS` et
   `CORS_EXTRA_ORIGINS` avec l'IP retenue (déjà pré-rempli avec
   `192.168.3.101` et `192.168.3.212` par défaut). Redémarrez Gunicorn :
   `sudo systemctl restart gunicorn`.
2. **Desktop** — ouvrez l'app → écran d'accueil → **⚙ Paramètres serveur**
   → entrez `http://<IP-fixe>:8000` (ou `http://pointageqr.local:8000` si
   avahi est configuré) → Tester → Enregistrer.
3. **Mobile** — ouvrez l'app → écran de configuration → entrez la même URL
   → Tester la connexion → Sauvegarder.

Une fois cette étape faite, l'IP ne devrait plus jamais changer (grâce à la
réservation DHCP), et même si elle change un jour, il suffit de refaire les
3 étapes ci-dessus — toujours sans toucher au code.

## Sécurité — à propos du fichier `.env`

Le fichier `.env` fourni contenait des secrets réels (clé Django, mot de
passe PostgreSQL) directement dans l'archive transmise. La clé `SECRET_KEY`
a été régénérée dans le cadre de cette mise à jour. Il est recommandé de
changer aussi le mot de passe PostgreSQL (`DB_PASSWORD`) côté base de
données ET dans `.env`, et de ne **jamais** committer ou partager ce fichier
(`.gitignore` l'exclut déjà correctement).
