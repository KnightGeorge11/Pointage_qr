// services/siteService.ts

import api from '../services/api'

export interface Site {
  id: number
  nom: string
  adresse?: string
  description?: string
}

class SiteService {
  async getSites(): Promise<Site[]> {
    return api.get<Site[]>('/mobile/sites/')
  }
}

export default new SiteService()