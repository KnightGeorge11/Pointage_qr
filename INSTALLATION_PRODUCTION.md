# Guide complet d'installation et de mise en production — Pointage QR

Guide de référence pour le dépôt Pointage_qr. Il couvre le backend Django/DRF, PostgreSQL, Gunicorn, Nginx, Web/Jazzmin, mobile Expo/React Native et desktop Python.

## 1. Architecture

Production recommandée :

~~~text
Navigateur / Mobile / Desktop
          |
          v
https://pointage.exemple.tld
          |
          v
       Nginx :443
          |
          v
Gunicorn -> pointage_qr.wsgi
          |
          v
        Django
          |
          v
     PostgreSQL
~~~

PostgreSQL et Gunicorn ne doivent pas être exposés directement à Internet.

Principaux éléments du dépôt :

- pointage/ : métier, modèles, vues, API et administration ;
- pointage_qr/ : configuration Django et WSGI ;
- requirements.txt : dépendances backend ;
- mobile/ScanMobileApp/ : client Expo/React Native ;
- desktop/ : client Python/Windows ;
- NETWORK_SETUP.md : réseau LAN ;
- .github/workflows/mobile-build.yml : build Android automatique.

## 2. Prérequis de mise en production

Ce guide commence avec un serveur de production déjà provisionné et administrable. Il ne couvre pas l'installation du système d'exploitation ni le choix d'un fournisseur.

Avant de déployer, vérifier que l'environnement cible dispose déjà de :

- Python compatible avec les dépendances du projet et `venv` ;
- PostgreSQL, avec un compte et une base dédiés ;
- Git pour récupérer le dépôt ;
- un service applicatif compatible WSGI (Gunicorn) ;
- un reverse proxy HTTPS (Nginx ou équivalent) ;
- un gestionnaire de services adapté à l'environnement, si systemd est utilisé dans les exemples ci-dessous ;
- un nom de domaine et un certificat TLS valides pour une exposition Internet.

Les commandes systemd, Nginx et Certbot ci-dessous sont des exemples pour un serveur Linux qui utilise ces outils. Sur une plateforme managée ou un autre environnement, appliquez les équivalents fournis par l'hébergeur. N'exposez jamais PostgreSQL ni Gunicorn directement à Internet.


## 3. Installer ou mettre à jour le dépôt

Première installation :

~~~bash
cd ~
git clone git@github.com:KnightGeorge11/Pointage_qr.git pointage_qr
cd pointage_qr
~~~

Mise à jour :

~~~bash
cd ~/pointage_qr
git pull origin main
~~~

Vérifier :

~~~bash
git branch --show-current
git status
~~~

## 4. Environnement Python

~~~bash
cd ~/pointage_qr
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
~~~

Dépendances principales actuelles : Django 5.2.17, DRF 3.17.2, django-cors-headers 4.9.0, django-jazzmin 3.0.3, psycopg2-binary 2.9.11, qrcode 8.2, Pillow 12.3.0, openpyxl 3.1.5 et Gunicorn 22.0.0.

## 5. PostgreSQL

Entrer dans PostgreSQL :

~~~bash
sudo -u postgres psql
~~~

Créer un utilisateur et une base dédiés :

~~~sql
CREATE USER pointage_user WITH PASSWORD 'MOT_DE_PASSE_TRES_FORT';
CREATE DATABASE pointage_qr OWNER pointage_user;
\q
~~~

Tester :

~~~bash
psql -h 127.0.0.1 -U pointage_user -d pointage_qr
~~~

Le port 5432 ne doit normalement pas être exposé à Internet.

## 6. Configuration .env

Le fichier .env est ignoré par Git. Ne jamais le publier.

Créer :

~~~bash
cd ~/pointage_qr
nano .env
~~~

Exemple de structure :

~~~dotenv
SECRET_KEY=UNE_VRAIE_CLE_SECRETE
DEBUG=False
ADMIN_SECRET_CODE=UN_CODE_SECRET

DJANGO_ALLOWED_HOSTS=pointage.exemple.tld,www.pointage.exemple.tld,127.0.0.1,localhost
CORS_EXTRA_ORIGINS=https://pointage.exemple.tld
CSRF_TRUSTED_ORIGINS=https://pointage.exemple.tld

DB_NAME=pointage_qr
DB_USER=pointage_user
DB_PASSWORD=MOT_DE_PASSE_POSTGRESQL
DB_HOST=127.0.0.1
DB_PORT=5432

SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=31536000
~~~

Générer une clé Django :

~~~bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
~~~

Ne jamais mettre dans Git : .env, SECRET_KEY, ADMIN_SECRET_CODE, DB_PASSWORD, tokens, clés privées TLS ou sauvegardes contenant des données réelles.

## 7. Vérifier Django et préparer la base

~~~bash
cd ~/pointage_qr
source venv/bin/activate
python manage.py check
python manage.py check --deploy
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput
~~~

Le projet utilise le modèle utilisateur pointage.CustomUser. Toujours utiliser les migrations du projet.

## 8. Tester Django avant Gunicorn

Test local uniquement :

~~~bash
python manage.py runserver 127.0.0.1:8000
~~~

Puis :

~~~bash
curl -I http://127.0.0.1:8000/
curl http://127.0.0.1:8000/api/mobile/test/
~~~

Arrêter runserver ensuite. Il ne doit jamais servir de serveur de production.

## 9. Gunicorn et systemd

Créer :

~~~bash
sudo nano /etc/systemd/system/gunicorn.service
~~~

Configuration correspondant à l'installation actuelle :

~~~ini
[Unit]
Description=Gunicorn daemon pour Pointage_qr
After=network.target

[Service]
User=adminserver
Group=www-data
WorkingDirectory=/home/adminserver/pointage_qr
ExecStart=/home/adminserver/pointage_qr/venv/bin/gunicorn --workers 3 --bind unix:/home/adminserver/pointage_qr/gunicorn.sock pointage_qr.wsgi:application

[Install]
WantedBy=multi-user.target
~~~

Activer :

~~~bash
sudo systemctl daemon-reload
sudo systemctl enable --now gunicorn
sudo systemctl status gunicorn --no-pager
~~~

Logs :

~~~bash
sudo journalctl -u gunicorn -n 100 --no-pager
~~~

Après modification du code ou du .env :

~~~bash
sudo systemctl restart gunicorn
~~~

## 10. Nginx

Créer :

~~~bash
sudo nano /etc/nginx/sites-available/pointage_qr
~~~

Configuration :

~~~nginx
server {
    listen 80;
    server_name pointage.exemple.tld;

    location = /favicon.ico {
        access_log off;
        log_not_found off;
    }

    location /static/ {
        alias /home/adminserver/pointage_qr/staticfiles/;
    }

    location /media/ {
        root /home/adminserver/pointage_qr;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/home/adminserver/pointage_qr/gunicorn.sock;
    }
}
~~~

Activer et tester :

~~~bash
sudo ln -s /etc/nginx/sites-available/pointage_qr /etc/nginx/sites-enabled/pointage_qr
sudo nginx -t
sudo systemctl reload nginx
~~~

## 11. Domaine, IP publique et NAT

Exemple de domaine :

~~~text
pointage.exemple.tld
~~~

DNS :

~~~text
A    pointage    -> IP_PUBLIQUE_DU_SERVEUR
~~~

Si le serveur Linux possède une IP privée, le routeur doit rediriger :

~~~text
TCP 80  -> IP_PRIVEE_DU_SERVEUR:80
TCP 443 -> IP_PRIVEE_DU_SERVEUR:443
~~~

Ne pas rediriger PostgreSQL 5432 ni un port Gunicorn.

## 12. HTTPS

Installer Certbot :

~~~bash
sudo apt install -y certbot python3-certbot-nginx
~~~

Après configuration DNS et accessibilité du port 80 :

~~~bash
sudo certbot --nginx -d pointage.exemple.tld
sudo certbot renew --dry-run
~~~

Valider HTTPS avant de configurer les clients en production.

## 13. Django HTTPS

Vérifier :

~~~dotenv
DEBUG=False
DJANGO_ALLOWED_HOSTS=pointage.exemple.tld
CORS_EXTRA_ORIGINS=https://pointage.exemple.tld
CSRF_TRUSTED_ORIGINS=https://pointage.exemple.tld
SECURE_SSL_REDIRECT=True
~~~

Puis :

~~~bash
sudo systemctl restart gunicorn
python manage.py check --deploy
~~~

Le projet active en production les cookies sécurisés, la protection MIME, la politique de référent et HSTS.

Ne pas utiliser une politique HSTS agressive avant d'avoir validé définitivement le domaine HTTPS.

## 14. API mobile

Routes principales :

| Méthode | Route | Auth |
|---|---|---|
| GET | /api/mobile/test/ | publique |
| POST | /api/mobile/auth/login/ | publique |
| POST | /api/mobile/auth/logout/ | Token |
| GET | /api/mobile/sites/ | Token |
| POST | /api/mobile/scan/check-first/ | Token |
| POST | /api/mobile/scan/record/ | Token |
| GET | /api/mobile/periods/current/ | Token |
| GET | /api/mobile/pointages/ | Token |
| GET | /api/mobile/pointages/today/ | Token |

Le endpoint test est public uniquement pour vérifier que Django est joignable. Les opérations métier sont protégées par TokenAuthentication.

## 15. Application mobile

Dossier : mobile/ScanMobileApp/

Installer :

~~~bash
cd mobile/ScanMobileApp
npm ci
~~~

Développement :

~~~bash
npm start
~~~

ou :

~~~bash
npm run android
~~~

URL LAN temporaire :

~~~text
http://192.168.x.x:8000
~~~

URL production :

~~~text
https://pointage.exemple.tld
~~~

Le mobile possède un test de connexion qui permet de vérifier une URL avant de la sauvegarder.

## 16. Build Android

Le projet contient eas.json avec les profils development, preview et production.

Configurer EAS :

~~~bash
cd mobile/ScanMobileApp
npx eas login
~~~

Build interne :

~~~bash
npx eas build --platform android --profile preview
~~~

Build production :

~~~bash
npx eas build --platform android --profile production
~~~

Le workflow .github/workflows/mobile-build.yml vérifie aussi automatiquement la compilation Android et publie un APK debug comme artefact.

Un APK debug GitHub n'est pas une release Android de production signée.

## 17. HTTP vers HTTPS sur mobile

app.json autorise actuellement le trafic HTTP clair Android afin de permettre les tests LAN.

Pour la production, utiliser uniquement :

~~~text
https://pointage.exemple.tld
~~~

Après migration HTTPS définitive, retirer l'autorisation HTTP clair et reconstruire l'application.

## 18. Application desktop

Dossier : desktop/

Technologies : Python, Tkinter, Requests, OpenCV, Pillow, PyInstaller et Keyring.

Windows :

~~~bat
cd desktop
python -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
~~~

L'écran Paramètres serveur permet de saisir et tester l'URL.

Le token desktop est stocké via keyring plutôt que dans le JSON de préférences en clair.

## 19. Build Windows

Sur Windows :

~~~bat
cd desktop
build_exe.bat
~~~

Résultat attendu :

~~~text
desktop/dist/PointageQR.exe
~~~

Tester l'exécutable avant distribution : connexion, webcam, QR, historique et logout/login.

## 20. Configuration métier initiale

Ouvrir :

~~~text
https://pointage.exemple.tld/admin/
~~~

Configurer :

1. comptes utilisateurs ;
2. employés ;
3. postes ;
4. sites ;
5. horaires ;
6. configuration globale du pointage ;
7. jours fériés ;
8. règles de garde ;
9. données nécessaires aux scans.

Le token opérateur mobile/desktop et le QR employé sont deux mécanismes indépendants.

## 21. Recette fonctionnelle

Web/Jazzmin :

- login ;
- dashboard ;
- navigation ;
- CRUD ;
- historique ;
- détail d'un pointage ;
- anomalies ;
- exports ;
- statistiques.

API :

~~~bash
curl https://pointage.exemple.tld/api/mobile/test/
~~~

Mobile :

- URL serveur ;
- test ;
- login ;
- site ;
- scan ;
- arrivée ;
- départ ;
- garde/nuit ;
- historique ;
- logout ;
- nouveau login.

Desktop :

- URL ;
- test ;
- login ;
- site ;
- webcam ;
- scan ;
- historique ;
- logout/login ;
- redémarrage.

## 22. Mise à jour du serveur

~~~bash
cd ~/pointage_qr
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check --deploy
sudo systemctl restart gunicorn
sudo nginx -t
sudo systemctl reload nginx
~~~

Puis vérifier :

~~~bash
sudo systemctl status gunicorn --no-pager
sudo systemctl status nginx --no-pager
~~~

Ne jamais supprimer la base pour résoudre une migration en erreur.

## 23. Sauvegardes

Base :

~~~bash
pg_dump -h 127.0.0.1 -U pointage_user -Fc pointage_qr > pointage_qr_$(date +%F).dump
~~~

Sauvegarder aussi :

~~~text
~/pointage_qr/media/
~~~

Stocker les sauvegardes sur un autre support ou serveur.

## 24. Restauration

Exemple :

~~~bash
createdb -h 127.0.0.1 -U pointage_user pointage_qr
pg_restore -h 127.0.0.1 -U pointage_user -d pointage_qr sauvegarde.dump
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart gunicorn
~~~

Restaurer également media/.

## 25. Pare-feu

Ports publics typiques :

- 80/tcp ;
- 443/tcp ;
- SSH selon politique de sécurité.

Ne pas exposer 5432, le socket Gunicorn ou runserver.

Exemple UFW, à adapter avant activation :

~~~bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
~~~

Une mauvaise règle SSH peut couper l'accès au serveur.

## 26. Diagnostic

Gunicorn :

~~~bash
sudo systemctl status gunicorn
sudo journalctl -u gunicorn -n 100 --no-pager
~~~

Nginx :

~~~bash
sudo nginx -t
sudo systemctl status nginx
sudo tail -n 100 /var/log/nginx/error.log
~~~

PostgreSQL :

~~~bash
sudo systemctl status postgresql
~~~

Ports :

~~~bash
sudo ss -lntp
~~~

Django :

~~~bash
source venv/bin/activate
python manage.py check --deploy
~~~

## 27. Dépannage

### DisallowedHost
Vérifier DJANGO_ALLOWED_HOSTS puis redémarrer Gunicorn.

### CSRF
Vérifier CSRF_TRUSTED_ORIGINS avec l'URL HTTPS exacte.

### 502 Bad Gateway
Vérifier le service Gunicorn, ses logs et l'existence de gunicorn.sock.

### CSS/JS absents
Relancer collectstatic, tester Nginx et recharger Nginx.

### Mobile inaccessible
Vérifier URL, test de connexion, endpoint /api/mobile/test/, DNS, NAT, HTTPS, réseau et firewall.

### HTTP 401 au login
Vérifier identifiants et état du compte.

### HTTP 401 pendant un scan
Le token n'est plus valide : logout/login.

## 28. LAN temporaire contre production

LAN :

~~~text
http://192.168.x.x:8000
~~~

Simple pour les tests mais dépend de l'IP et n'est pas adapté à Internet.

Production :

~~~text
https://pointage.exemple.tld
~~~

URL stable, HTTPS et clients indépendants de l'IP privée.

## 29. Ordre recommandé pour une première mise en production

Le serveur et les services de base sont supposés déjà provisionnés. Adapter les commandes aux outils réellement disponibles sur l'environnement cible.

1. Vérifier l'accès administrateur au serveur et la disponibilité de Python, Git et PostgreSQL.
2. Vérifier que la base et l'utilisateur PostgreSQL dédiés existent.
3. Cloner le dépôt ou récupérer la version validée à déployer.
4. Créer l'environnement virtuel Python.
5. Installer les dépendances de `requirements.txt`.
6. Créer le fichier `.env` privé avec les secrets et paramètres de production.
7. Vérifier la connexion à PostgreSQL.
8. Exécuter `python manage.py check`.
9. Sauvegarder la base existante avant toute mise à jour d'une installation déjà utilisée.
10. Exécuter `python manage.py migrate`.
11. Créer le superutilisateur si c'est une nouvelle installation.
12. Exécuter `python manage.py collectstatic --noinput`.
13. Vérifier `python manage.py check --deploy` et corriger les avertissements applicables.
14. Configurer le serveur WSGI et le gestionnaire de services disponibles sur la plateforme.
15. Configurer le reverse proxy et le domaine.
16. Valider DNS, HTTPS et le renouvellement du certificat.
17. Tester l'application Web/Jazzmin et l'endpoint `/api/mobile/test/`.
18. Configurer les clients mobile et desktop avec l'URL HTTPS réelle.
19. Tester connexion, déconnexion, nouvelle connexion et scans avec des comptes de test.
20. Construire et tester les versions distribuables mobile et desktop.
21. Mettre en place les sauvegardes et tester la procédure de restauration.
22. Documenter la version déployée et la procédure de retour arrière.

Les commandes Linux, systemd, Nginx et Certbot des sections précédentes sont des exemples, pas une exigence d'utiliser Ubuntu. Sur une plateforme managée, utilisez les services équivalents proposés par l'hébergeur.

## 30. Sécurité essentielle

Ne pas :

- committer .env ;
- mettre des mots de passe dans le code ;
- stocker des tokens en clair ;
- exposer PostgreSQL ;
- utiliser runserver en production ;
- exposer Gunicorn ;
- mettre DEBUG=True en production ;
- supprimer la base pour réparer une migration ;
- considérer un APK debug comme une release finale.

Toujours :

- sauvegarder PostgreSQL ;
- sauvegarder media/ ;
- exécuter check --deploy ;
- tester API et authentification ;
- tester un vrai scan ;
- vérifier les logs ;
- tester les clients après changement réseau ;
- conserver une procédure de retour arrière.

## 31. Architecture finale

~~~text
Internet
   |
 HTTPS :443
   |
DNS pointage.exemple.tld
   |
Routeur / Firewall
   |
Nginx
   |
Gunicorn
   |
Django 5.2
   |---- Web utilisateur
   |---- Jazzmin /admin/
   |---- DRF /api/mobile/
   |          |---- Mobile Expo
   |          |---- Desktop Python
   |
PostgreSQL
~~~

Une fois cette architecture en place, les clients utilisent l'URL HTTPS stable et n'ont plus besoin de connaître l'IP privée du serveur.

## 32. Fichiers importants

| Fichier | Rôle |
|---|---|
| manage.py | commandes Django |
| pointage/ | application métier et API |
| pointage_qr/settings.py | configuration Django |
| pointage_qr/urls.py | routes principales |
| pointage_qr/wsgi.py | entrée Gunicorn |
| requirements.txt | dépendances backend |
| static/ | sources statiques |
| media/ | médias |
| mobile/ScanMobileApp/ | application mobile |
| mobile/ScanMobileApp/app.json | configuration Expo/Android |
| mobile/ScanMobileApp/eas.json | profils EAS |
| mobile/ScanMobileApp/src/services/api.ts | client API mobile |
| desktop/ | application desktop |
| desktop/api_client.py | client API desktop |
| desktop/storage.py | stockage local desktop |
| desktop/build_exe.bat | build Windows |
| .github/workflows/mobile-build.yml | build Android automatique |
| NETWORK_SETUP.md | configuration réseau LAN |

## Conclusion

Le projet est déjà structuré pour une production classique :

PostgreSQL -> Django -> Gunicorn -> Nginx -> HTTPS -> Web/Mobile/Desktop.

La mise en production consiste principalement à préparer le serveur, sécuriser PostgreSQL et Django, publier Django derrière Nginx/HTTPS, puis configurer les clients avec l'URL HTTPS stable.

Pour une nouvelle installation, suivre l'ordre de la section 29 plutôt que d'appliquer des commandes isolées.
