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
  RefreshControl,
} from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { useNavigation } from '@react-navigation/native'
import { Ionicons } from '@expo/vector-icons'
import { apiService, Site } from '../services/api'
import { useAppContext } from '../context/AppContext'
import { colors } from '../theme/colors'

const SiteSelectionScreen = () => {
  const navigation = useNavigation<any>()

  // ✅ Hook DOIT être ici
  const { setSelectedSite: setGlobalSelectedSite, setSites: setGlobalSites } = useAppContext()

  const [sites, setSites] = useState<Site[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [selectedSite, setSelectedSite] = useState<Site | null>(null)
  const [connectionError, setConnectionError] = useState<string | null>(null)

  useEffect(() => {
    initialize()
  }, [])

  const initialize = async () => {
    await loadSelectedSite()
    await loadSites()
    await apiService.syncPendingScans()
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
          <Ionicons name="location" size={24} color={colors.blue} />
          <View style={styles.siteText}>
            <Text style={styles.siteName}>{item.nom}</Text>
            {item.adresse && (
              <Text style={styles.siteAddress}>{item.adresse}</Text>
            )}
          </View>
        </View>

        {isSelected && (
          <Ionicons name="checkmark-circle" size={24} color={colors.blue} />
        )}
      </TouchableOpacity>
    )
  }

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color={colors.blue} />
        <Text style={styles.status}>Connexion au serveur...</Text>
      </View>
    )
  }

  if (connectionError && sites.length === 0) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.centered}>
          <Ionicons name="cloud-offline-outline" size={48} color={colors.inkMuted} />
          <Text style={styles.errorTitle}>Impossible de contacter le serveur</Text>
          <Text style={styles.errorDetail}>{connectionError}</Text>
          <TouchableOpacity style={styles.retryButton} onPress={() => { setLoading(true); loadSites() }}>
            <Ionicons name="refresh-outline" size={18} color={colors.white} />
            <Text style={styles.retryText}>Réessayer</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.configButton} onPress={() => navigation.navigate('Config')}>
            <Text style={styles.configText}>Vérifier l'adresse du serveur</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
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
  container: { flex: 1, backgroundColor: colors.surface },
  siteItem: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    backgroundColor: colors.white,
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
  },
  selectedItem: { backgroundColor: colors.blueDim },
  siteInfo: { flexDirection: 'row', alignItems: 'center', flex: 1 },
  siteText: { marginLeft: 16 },
  siteName: { fontSize: 16, fontWeight: 'bold' },
  siteAddress: { fontSize: 14, color: colors.inkMuted },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 32 },
  status: { marginTop: 8, fontSize: 16, color: colors.inkMuted },
  errorTitle: { marginTop: 14, fontSize: 16, fontWeight: '600', color: colors.ink, textAlign: 'center' },
  errorDetail: { marginTop: 6, fontSize: 13, color: colors.inkMuted, textAlign: 'center' },
  retryButton: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    backgroundColor: colors.ink, paddingHorizontal: 20, paddingVertical: 12,
    borderRadius: 10, marginTop: 20,
  },
  retryText: { color: colors.white, fontWeight: '600', fontSize: 14 },
  configButton: { marginTop: 14 },
  configText: { color: colors.blue, fontSize: 14, fontWeight: '500' },
  list: { padding: 16 },
})

export default SiteSelectionScreen