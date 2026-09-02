// IP fixe du serveur (voir NETWORK_SETUP.md — réservation DHCP recommandée
// pour que cette adresse reste stable). Si l'IP change à nouveau, préférez
// mettre à jour l'écran "Configuration" de l'app plutôt que ce fichier :
// une valeur enregistrée dans AsyncStorage prime toujours sur ce défaut,
// donc modifier cette constante seule ne suffit pas pour une app déjà
// installée et configurée.
export const DEFAULT_API_URL = 'http://192.168.3.101:8000';
export const STORAGE_KEYS = {
  API_URL: 'api_url',
  API_TOKEN: 'api_token',
  CURRENT_USER: 'current_user',
  SELECTED_SITE: 'selected_site',
  CACHED_SITES: 'cached_sites',
  CACHED_SITES_TIMESTAMP: 'cached_sites_timestamp',
  PENDING_SCANS: 'pending_scans',
};
