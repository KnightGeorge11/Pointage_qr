import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { DEFAULT_API_URL, STORAGE_KEYS } from '../utils/constants';

export interface Site {
  id: number;
  nom: string;
  adresse?: string;
  heure_ouverture_matin?: string;
  heure_fermeture_matin?: string;
  heure_ouverture_apres_midi?: string;
  heure_fermeture_apres_midi?: string;
}

export interface Employee {
  id: number;
  nom_complet: string;
  matricule: string;
  poste?: string;
}

export interface ApiResponse {
  status: 'success' | 'error';
  message?: string;
  data: any;
}

export interface ApiStatus {
  connected: boolean;
  baseUrl: string;
  lastCheck?: Date | null;
  environment?: string;
}

export interface ConnectionTestResult {
  success: boolean;
  message?: string;
  url?: string;
  responseTime?: number;
}

export interface CheckFirstScanResponse {
  first_scan: boolean;
  periode: string;
  date: string;
  garde_planifiee: boolean;
  garde_en_cours: boolean;
  employe: Employee;
  site: {
    id: number;
    nom: string;
  };
}

export interface TodayPointage {
  id: number;
  employe_nom: string;
  employe_matricule: string;
  employe_poste?: string;
  site?: string;
  site_id?: number;
  date_pointage: string;
  periode: 'matin' | 'apres_midi' | 'nuit';
  type_journee: 'normal' | 'garde';
  heure_arrivee?: string;
  heure_depart?: string;
  retard?: string;
  heures_travaillees?: string;
  statut: string;
}

const getBaseUrl = async (): Promise<string> => {
  try {
    const stored = await AsyncStorage.getItem(STORAGE_KEYS.API_URL);
    return stored || DEFAULT_API_URL;
  } catch {
    return DEFAULT_API_URL;
  }
};

const createApi = (baseURL: string) => axios.create({
  baseURL,
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  },
});

let api = createApi(DEFAULT_API_URL);

const refreshApi = async () => {
  const url = await getBaseUrl();
  api = createApi(url);
};

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (!error.response) {
      if (error.code === 'ECONNABORTED') {
        error.message = 'Timeout : le serveur ne répond pas';
      } else {
        error.message = 'Impossible de joindre le serveur';
      }
    }
    return Promise.reject(error);
  }
);

export const testConnection = async (): Promise<ConnectionTestResult> => {
  const startTime = Date.now();
  try {
    const response = await api.get('/api/mobile/test/', { timeout: 10000 });
    const responseTime = Date.now() - startTime;
    if (response.data?.status === 'success') {
      return { success: true, message: 'Connecté', url: api.defaults.baseURL, responseTime };
    }
    return { success: false, message: 'Réponse inattendue du serveur', url: api.defaults.baseURL, responseTime };
  } catch (error: any) {
    return {
      success: false,
      message: error.message || 'Erreur inconnue',
      url: api.defaults.baseURL,
      responseTime: Date.now() - startTime,
    };
  }
};

export const checkStatus = async (): Promise<ApiStatus> => {
  const result = await testConnection();
  return {
    connected: result.success,
    baseUrl: api.defaults.baseURL || DEFAULT_API_URL,
    lastCheck: new Date(),
  };
};

export const initializeApi = async (): Promise<boolean> => {
  await refreshApi();
  const result = await testConnection();
  return result.success;
};

export const setBaseUrl = async (url: string): Promise<void> => {
  const cleanUrl = url.replace(/\/+$/, '');
  await AsyncStorage.setItem(STORAGE_KEYS.API_URL, cleanUrl);
  api = createApi(cleanUrl);
};

export const getCurrentServerUrl = (): string => {
  return api.defaults.baseURL || DEFAULT_API_URL;
};

export const apiService = {
  initialize: initializeApi,
  testConnection,
  checkStatus,
  setBaseUrl,
  getCurrentServerUrl,

  async isServerAvailable(): Promise<boolean> {
    const result = await testConnection();
    return result.success;
  },

  async getSites(): Promise<Site[]> {
    const cachedSites = await AsyncStorage.getItem(STORAGE_KEYS.CACHED_SITES);
    const cacheTimestamp = await AsyncStorage.getItem(STORAGE_KEYS.CACHED_SITES_TIMESTAMP);
    const cacheValid = cacheTimestamp && Date.now() - parseInt(cacheTimestamp) < 300_000;

    if (cachedSites && cacheValid) {
      return JSON.parse(cachedSites);
    }

    try {
      const response = await api.get<ApiResponse>('/api/mobile/sites/');
      if (response.data.status === 'success' && Array.isArray(response.data.data)) {
        const sites: Site[] = response.data.data;
        await AsyncStorage.setItem(STORAGE_KEYS.CACHED_SITES, JSON.stringify(sites));
        await AsyncStorage.setItem(STORAGE_KEYS.CACHED_SITES_TIMESTAMP, Date.now().toString());
        return sites;
      }
      throw new Error(response.data.message || 'Erreur récupération des sites');
    } catch (error: any) {
      if (cachedSites) {
        return JSON.parse(cachedSites);
      }
      throw error;
    }
  },

  async syncSites(): Promise<Site[]> {
    await AsyncStorage.removeItem(STORAGE_KEYS.CACHED_SITES);
    await AsyncStorage.removeItem(STORAGE_KEYS.CACHED_SITES_TIMESTAMP);
    return this.getSites();
  },

  async checkFirstScan(matricule: string, siteId: number): Promise<CheckFirstScanResponse> {
    const response = await api.post<ApiResponse>('/api/mobile/scan/check-first/', {
      employee_qr: matricule,
      site_id: siteId,
    });
    if (response.data.status === 'success') return response.data.data;
    throw new Error(response.data.message || 'Erreur vérification scan');
  },

  async recordScan(
    employeeQr: string,
    siteId: number,
    mode: 'day' | 'night' = 'day',
    options: {
      forceSortie?: boolean;
      confirmerAutorisation?: boolean;
      forceNew?: boolean;
    } = {}
  ): Promise<any> {
    const response = await api.post('/api/mobile/scan/record/', {
      employee_qr:            employeeQr,
      site_id:                siteId,
      mode,
      force_sortie:           options.forceSortie           ?? false,
      confirmer_autorisation: options.confirmerAutorisation ?? false,
      force_new:              options.forceNew              ?? false,
    });
    return response.data;
  },

  async getCurrentPeriod(): Promise<any> {
    const response = await api.get<ApiResponse>('/api/mobile/periods/current/');
    if (response.data.status === 'success') return response.data.data;
    throw new Error(response.data.message || 'Erreur période');
  },

  async saveSelectedSite(site: Site): Promise<void> {
    await AsyncStorage.setItem(STORAGE_KEYS.SELECTED_SITE, JSON.stringify(site));
  },

  async getSelectedSite(): Promise<Site | null> {
    const str = await AsyncStorage.getItem(STORAGE_KEYS.SELECTED_SITE);
    return str ? JSON.parse(str) : null;
  },

  async clearSelectedSite(): Promise<void> {
    await AsyncStorage.removeItem(STORAGE_KEYS.SELECTED_SITE);
  },

  async getEmployeePointages(matricule: string, date?: string): Promise<any> {
    let url = `/api/mobile/pointages/?matricule=${encodeURIComponent(matricule)}`;
    if (date) url += `&date=${date}`;
    const response = await api.get(url);
    if (response.data.status === 'success') return response.data.data;
    throw new Error(response.data.message || 'Erreur pointages');
  },

  async getTodayPointages(siteId?: number | null, date?: string): Promise<{
    count: number;
    date: string;
    data: TodayPointage[];
  }> {
    let url = '/api/mobile/pointages/today/';
    const params: string[] = [];
    if (siteId) params.push(`site_id=${siteId}`);
    if (date)   params.push(`date=${date}`);
    if (params.length) url += '?' + params.join('&');
    const response = await api.get(url);
    if (response.data.status === 'success') return response.data;
    throw new Error(response.data.message || 'Erreur journal du jour');
  },

  async getServerStatus(): Promise<{ status: string; timestamp: string }> {
    try {
      const response = await api.get('/api/mobile/test/');
      return { status: response.data.status, timestamp: new Date().toISOString() };
    } catch {
      return { status: 'offline', timestamp: new Date().toISOString() };
    }
  },
};

export { api, getBaseUrl };