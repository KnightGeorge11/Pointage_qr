import React, { createContext, useContext, useState, useEffect } from 'react'
import AsyncStorage from '@react-native-async-storage/async-storage'
import { Site } from '../services/api'
import { DEFAULT_API_URL, STORAGE_KEYS } from '../utils/constants'

export type ApiStatus = {
  connected: boolean
  baseUrl: string
  lastCheck?: Date | null
  environment?: string
}

type AppContextType = {
  selectedSite: Site | null
  setSelectedSite: (site: Site | null) => void
  sites: Site[]
  setSites: (sites: Site[]) => void
  apiStatus: ApiStatus
  setApiStatus: (status: ApiStatus) => void
}

const AppContext = createContext<AppContextType | undefined>(undefined)

export const AppProvider = ({ children }: any) => {
  const [selectedSite, setSelectedSiteState] = useState<Site | null>(null)
  const [sites, setSites] = useState<Site[]>([])
  const [apiStatus, setApiStatus] = useState<ApiStatus>({
    connected: true,
    baseUrl: DEFAULT_API_URL,
  })

  useEffect(() => {
    const loadSavedData = async () => {
      try {
        const saved = await AsyncStorage.getItem(STORAGE_KEYS.SELECTED_SITE)
        if (saved) {
          setSelectedSiteState(JSON.parse(saved))
        }
        const savedUrl = await AsyncStorage.getItem(STORAGE_KEYS.API_URL)
        if (savedUrl) {
          setApiStatus(prev => ({ ...prev, baseUrl: savedUrl }))
        }
      } catch (err) {
        console.error('Erreur chargement données:', err)
      }
    }
    loadSavedData()
  }, [])

  const setSelectedSite = async (site: Site | null) => {
    try {
      if (site) {
        await AsyncStorage.setItem(STORAGE_KEYS.SELECTED_SITE, JSON.stringify(site))
      } else {
        await AsyncStorage.removeItem(STORAGE_KEYS.SELECTED_SITE)
      }
      setSelectedSiteState(site)
    } catch (err) {
      console.error('Erreur setSelectedSite:', err)
    }
  }

  return (
    <AppContext.Provider
      value={{
        selectedSite,
        setSelectedSite,
        sites,
        setSites,
        apiStatus,
        setApiStatus,
      }}
    >
      {children}
    </AppContext.Provider>
  )
}

export const useAppContext = () => {
  const context = useContext(AppContext)
  if (!context) {
    throw new Error('useAppContext must be used inside AppProvider')
  }
  return context
}
