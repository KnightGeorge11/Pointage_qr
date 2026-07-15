// screens/SiteSelectionScreen.tsx

import React, { useState, useEffect, useCallback } from 'react'
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  Alert,
  ActivityIndicator,
  TextInput,
  Modal,
  RefreshControl,
} from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { useNavigation } from '@react-navigation/native'
import { Ionicons } from '@expo/vector-icons'
import { apiService, Site } from '../services/api'
import { useAppContext } from '../context/AppContext'

const SiteSelectionScreen = () => {
  const navigation = useNavigation<any>()

  // ✅ Hook DOIT être ici
  const { setSelectedSite: setGlobalSelectedSite, setSites: setGlobalSites } = useAppContext()

  const [sites, setSites] = useState<Site[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [selectedSite, setSelectedSite] = useState<Site | null>(null)
  const [connectionError, setConnectionError] = useState<string | null>(null)
  const [showUrlConfig, setShowUrlConfig] = useState(false)
  const [customUrl, setCustomUrl] = useState('')

  useEffect(() => {
    initialize()
  }, [])

  const initialize = async () => {
    await loadSelectedSite()
    await loadSites()
  }

  const loadSelectedSite = async () => {
    try {
      const site = await apiService.getSelectedSite()
      setSelectedSite(site)
    } catch (error) {
      console.log('Erreur récupération site sélectionné:', error)
    }
  }

  const loadSites = async () => {
    try {
      setConnectionError(null)
      const data = await apiService.getSites()
      setSites(data)
      setGlobalSites(data)
    } catch (error: any) {
      console.log('Erreur chargement sites:', error)
      setConnectionError(error.message || 'Erreur de connexion')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  const onRefresh = useCallback(() => {
    setRefreshing(true)
    loadSites()
  }, [])

  // ✅ ICI la vraie correction
  const handleSelectSite = async (site: Site) => {
    try {
      await apiService.saveSelectedSite(site)

      setSelectedSite(site)          // état local (UI)
      setGlobalSelectedSite(site)   // 🔥 état global (Context)

      Alert.alert(
        'Succès',
        `Site "${site.nom}" sélectionné`,
        [
          {
            text: 'Scanner',
            onPress: () => navigation.navigate('Scan'),
          },
          { text: 'OK' },
        ]
      )
    } catch (error) {
      Alert.alert('Erreur', 'Impossible de sauvegarder la sélection')
    }
  }

  const renderItem = ({ item }: { item: Site }) => {
    const isSelected = selectedSite?.id === item.id

    return (
      <TouchableOpacity
        style={[styles.siteItem, isSelected && styles.selectedItem]}
        onPress={() => handleSelectSite(item)}
      >
        <View style={styles.siteInfo}>
          <Ionicons name="location" size={24} color="#007AFF" />
          <View style={styles.siteText}>
            <Text style={styles.siteName}>{item.nom}</Text>
            {item.adresse && (
              <Text style={styles.siteAddress}>{item.adresse}</Text>
            )}
          </View>
        </View>

        {isSelected && (
          <Ionicons name="checkmark-circle" size={24} color="#007AFF" />
        )}
      </TouchableOpacity>
    )
  }

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color="#007AFF" />
        <Text style={styles.status}>Connexion au serveur...</Text>
      </View>
    )
  }

  return (
    <SafeAreaView style={styles.container}>
      <FlatList
        data={sites}
        keyExtractor={(item) => item.id.toString()}
        renderItem={renderItem}
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
          />
        }
      />
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F5F5F5' },
  siteItem: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    backgroundColor: '#FFFFFF',
    borderBottomWidth: 1,
    borderBottomColor: '#E0E0E0',
  },
  selectedItem: { backgroundColor: '#E0F7FA' },
  siteInfo: { flexDirection: 'row', alignItems: 'center', flex: 1 },
  siteText: { marginLeft: 16 },
  siteName: { fontSize: 16, fontWeight: 'bold' },
  siteAddress: { fontSize: 14, color: '#757575' },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  status: { marginTop: 8, fontSize: 16, color: '#757575' },
  list: { padding: 16 },
})

export default SiteSelectionScreen