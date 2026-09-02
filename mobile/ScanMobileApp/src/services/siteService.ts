// services/siteService.ts

import { api } from './api'

export interface Site {
  id: number
  nom: string
  adresse?: string
  description?: string
}

interface SitesResponse {
  status: 'success' | 'error'
  message?: string
  data: Site[]
}

class SiteService {
  async getSites(): Promise<Site[]> {
    const response = await api.get<SitesResponse>('/api/mobile/sites/')
    if (response.data.status !== 'success' || !Array.isArray(response.data.data)) {
      throw new Error(response.data.message || 'Erreur récupération des sites')
    }
    return response.data.data
  }
}

export default new SiteService()
