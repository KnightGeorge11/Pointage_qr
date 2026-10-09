# Configuration réseau — Pointage QR

Ce document décrit la configuration réseau pour deux cas différents :
- **LAN / essais internes** : le client et le serveur sont sur le même réseau ;
- **production Internet** : les clients utilisent un domaine HTTPS stable.

Pour une production accessible depuis Internet, privilégiez un nom de domaine HTTPS. Une IP privée telle que `192.168.x.x` n'est pas une adresse publique et ne doit pas être utilisée comme URL Internet.

## 1. Configuration de l'URL côté client

Les applications mobile et desktop permettent de configurer l'URL de l'API depuis leurs écrans de paramètres. Utilisez l'URL correspondant réellement à votre environnement :

- LAN de test : `http://<IP-LAN-DU-SERVEUR>:8000` si le serveur Django est volontairement accessible sur ce port dans le réseau local ;
- production : `https://<votre-domaine>`.

Testez la connexion depuis l'application et enregistrez l'URL. L'application mobile conserve l'URL choisie dans son stockage local ; une déconnexion du compte ne doit pas nécessiter de reconfigurer le serveur.

La valeur `DEFAULT_API_URL` dans `mobile/ScanMobileApp/src/utils/constants.ts` est uniquement une valeur initiale pour une nouvelle installation. Une URL déjà enregistrée par l'utilisateur peut primer sur cette valeur. Ne changez pas cette constante pour corriger une installation existante sans vérifier le stockage local.

## 2. Configuration Django

Le serveur lit les hôtes autorisés depuis `DJANGO_ALLOWED_HOSTS`. Les origines CORS sont configurées par `CORS_EXTRA_ORIGINS` et les origines CSRF de confiance par `CSRF_TRUSTED_ORIGINS`. Définissez ces variables dans l'environnement de déploiement ou le fichier `.env` privé, en utilisant les valeurs adaptées à l'environnement.

Exemple de production avec domaine :

```dotenv
DJANGO_ALLOWED_HOSTS=pointage.exemple.tld
CORS_EXTRA_ORIGINS=https://pointage.exemple.tld
CSRF_TRUSTED_ORIGINS=https://pointage.exemple.tld
```

Remplacez `pointage.exemple.tld` par le vrai domaine. Ne copiez pas cet exemple tel quel. Après modification de la configuration serveur, redémarrez le service applicatif selon votre environnement et vérifiez les journaux.

Ne commitez jamais le fichier `.env`, les mots de passe, les clés secrètes ou les jetons d'accès.

## 3. LAN : conserver une adresse stable

Si le serveur est une VM ou une machine dans un réseau local, une réservation DHCP dans le routeur peut stabiliser son adresse :

1. Relevez l'adresse MAC de l'interface réseau du serveur.
2. Dans le routeur, associez cette adresse MAC à une adresse libre via la réservation DHCP.
3. Vérifiez que le serveur a bien reçu l'adresse réservée et que les clients peuvent joindre l'API.

Les outils de configuration réseau dépendent du système d'exploitation et de l'hyperviseur. N'appliquez pas de commande réseau spécifique sans vérifier qu'elle correspond à l'environnement : une mauvaise configuration peut rendre le serveur inaccessible.

Une IP statique configurée directement sur le serveur est aussi possible, mais elle doit être compatible avec le sous-réseau et exclue de la plage DHCP distribuée afin d'éviter les conflits.

## 4. Nom local et mDNS

Un nom local tel que `pointageqr.local` peut être pratique dans certains réseaux, si le serveur et les clients prennent en charge la résolution mDNS. Cette résolution n'est pas garantie sur tous les systèmes, notamment dans toutes les configurations Android.

Ne faites donc pas dépendre une production critique uniquement d'un nom `.local`. Pour l'accès Internet, utilisez un domaine public avec HTTPS.

## 5. Sécurité réseau

- N'exposez pas PostgreSQL (port 5432) à Internet.
- N'exposez pas directement Gunicorn ni le serveur de développement Django.
- Pour la production Internet, publiez l'application derrière un reverse proxy HTTPS.
- N'autorisez le port 8000 que si cela est nécessaire aux tests LAN, et uniquement sur le réseau de confiance.
- N'activez pas de redirection de ports sur le routeur sans comprendre sa portée et son impact de sécurité.

## 6. Diagnostic rapide

1. Depuis l'application, lancez le test de connexion sur l'URL exacte.
2. Vérifiez que le serveur répond à `/api/mobile/test/`.
3. Vérifiez l'adresse IP ou le DNS, le routage, le pare-feu et, pour Internet, le certificat TLS.
4. Si Django renvoie `DisallowedHost`, vérifiez `DJANGO_ALLOWED_HOSTS`.
5. Si le navigateur signale une erreur CSRF, vérifiez `CSRF_TRUSTED_ORIGINS`.
6. Si l'API répond mais le client échoue, vérifiez les journaux et l'URL réellement enregistrée dans les paramètres de l'application.
