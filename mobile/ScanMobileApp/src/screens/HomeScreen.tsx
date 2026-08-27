// src/screens/HomeScreen.tsx
import React, { useEffect, useState } from 'react'
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { useAppContext } from '../context/AppContext'
import { colors, radius } from '../theme/colors'

const HomeScreen = ({ navigation }: any) => {
  const { apiStatus, selectedSite } = useAppContext()
  const [currentTime, setCurrentTime] = useState(new Date())

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  const handleSitePress = () => navigation.navigate('SiteSelectionScreen')
  const handleScanPress = () => {
    if (!selectedSite) {
      navigation.navigate('SiteSelectionScreen')
      return
    }
    navigation.navigate('Scan')
  }
  const handleHistoryPress = () => navigation.navigate('History')

  return (
    <View style={styles.container}>
      {/* Status API */}
      <View style={[styles.card, styles.statusCard]}>
        <View
          style={[
            styles.statusDot,
            { backgroundColor: apiStatus.connected ? colors.green : colors.red },
          ]}
        />
        <Text style={styles.statusText}>
          {apiStatus.connected ? "Connecté à l'API" : 'Déconnecté'}
        </Text>
      </View>

      {/* Site sélectionné */}
      <TouchableOpacity
        style={[styles.card, styles.siteCard]}
        onPress={handleSitePress}
      >
        <Ionicons name="location-outline" size={22} color={colors.inkMuted} />
        <View style={{ flex: 1, marginLeft: 12 }}>
          <Text style={styles.siteLabel}>Site actuel</Text>
          <Text style={styles.siteText}>
            {selectedSite ? selectedSite.nom : 'Aucun site sélectionné'}
          </Text>
        </View>
        <Ionicons name="chevron-forward" size={20} color={colors.inkMuted} />
      </TouchableOpacity>

      {/* Horloge */}
      <View style={[styles.card, styles.clockCard]}>
        <Text style={styles.clockText}>{currentTime.toLocaleTimeString()}</Text>
        <Text style={styles.clockDate}>
          {currentTime.toLocaleDateString('fr-FR', {
            weekday: 'long',
            day: 'numeric',
            month: 'long',
          })}
        </Text>
      </View>

      {/* Actions */}
      <View style={styles.actionsContainer}>
        <TouchableOpacity
          style={[styles.actionButton, styles.scanButton]}
          onPress={handleScanPress}
        >
          <Ionicons name="qr-code-outline" size={30} color={colors.white} />
          <Text style={styles.actionText}>Scanner</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.actionButton, styles.historyButton]}
          onPress={handleHistoryPress}
        >
          <Ionicons name="reader-outline" size={30} color={colors.ink} />
          <Text style={[styles.actionText, { color: colors.ink }]}>
            Historique
          </Text>
        </TouchableOpacity>
      </View>
    </View>
  )
}

export default HomeScreen

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 20,
    backgroundColor: colors.surface,
  },

  // Cards
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    borderRadius: radius.lg,
    backgroundColor: colors.white,
    marginBottom: 12,
    shadowColor: '#000',
    shadowOpacity: 0.05,
    shadowOffset: { width: 0, height: 2 },
    shadowRadius: 8,
    elevation: 2,
  },

  // Status
  statusCard: {},
  statusDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  statusText: {
    marginLeft: 10,
    fontSize: 14,
    fontWeight: '500',
    color: colors.inkMuted,
  },

  // Site
  siteCard: { justifyContent: 'space-between' },
  siteLabel: {
    fontSize: 11,
    color: colors.inkMuted,
    fontWeight: '500',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  siteText: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.ink,
    marginTop: 2,
  },

  // Horloge
  clockCard: {
    flexDirection: 'column',
    alignItems: 'flex-start',
    paddingVertical: 20,
  },
  clockText: {
    fontSize: 38,
    fontWeight: '300',
    color: colors.ink,
    letterSpacing: 1,
  },
  clockDate: {
    fontSize: 13,
    color: colors.inkMuted,
    marginTop: 4,
    textTransform: 'capitalize',
  },

  // Actions
  actionsContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 8,
    gap: 12,
  },
  actionButton: {
    flex: 1,
    borderRadius: radius.lg,
    paddingVertical: 28,
    alignItems: 'center',
    justifyContent: 'center',
  },
  scanButton: {
    backgroundColor: colors.ink,
  },
  historyButton: {
    backgroundColor: colors.white,
    shadowColor: '#000',
    shadowOpacity: 0.05,
    shadowOffset: { width: 0, height: 2 },
    shadowRadius: 8,
    elevation: 2,
  },
  actionText: {
    marginTop: 10,
    color: colors.white,
    fontSize: 15,
    fontWeight: '600',
  },
})