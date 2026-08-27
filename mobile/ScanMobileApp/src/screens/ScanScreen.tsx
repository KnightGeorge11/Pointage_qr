// src/screens/ScanScreen.tsx
import React, { useEffect, useState, useCallback, useRef } from 'react'
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Alert,
  ActivityIndicator,
} from 'react-native'
import { CameraView, useCameraPermissions } from 'expo-camera'
import { Ionicons } from '@expo/vector-icons'
import { useAppContext } from '../context/AppContext'
import { apiService } from '../services/api'
import { colors, radius } from '../theme/colors'

export default function ScanScreen() {
  const { selectedSite } = useAppContext()
  const [mode, setMode] = useState<'day' | 'night'>('day')
  const [permission, requestPermission] = useCameraPermissions()
  const [scanned, setScanned] = useState(false)
  const [loading, setLoading] = useState(false)
  const [hint, setHint] = useState('Placez le QR code dans le cadre')

  // Référence pour éviter les appels multiples et les fuites mémoire
  const isMounted = useRef(true)
  const permissionRequested = useRef(false)

  // Nettoyage du composant
  useEffect(() => {
    return () => {
      isMounted.current = false
    }
  }, [])

  // Gestion propre des permissions
  useEffect(() => {
    if (!permission) {
      // Permission encore en cours de chargement
      return
    }

    if (!permission.granted && !permissionRequested.current) {
      permissionRequested.current = true
      console.log('[ScanScreen] Demande de permission caméra')
      requestPermission()
    }
  }, [permission, requestPermission])

  // ÉTAT 1 : Permission en cours de chargement
  if (permission === null || permission === undefined) {
    return (
      <View style={styles.permissionContainer}>
        <ActivityIndicator size="large" color={colors.ink} />
        <Text style={styles.permissionText}>Initialisation de la caméra...</Text>
      </View>
    )
  }

  // ÉTAT 2 : Permission refusée
  if (!permission.granted) {
    return (
      <View style={styles.permissionContainer}>
        <Ionicons name="camera-outline" size={48} color={colors.inkMuted} />
        <Text style={styles.permissionText}>Permission caméra requise</Text>
        <Text style={styles.permissionSubText}>
          L'application a besoin d'accéder à votre caméra pour scanner les QR codes.
        </Text>
        <TouchableOpacity
          style={styles.permissionButton}
          onPress={() => {
            permissionRequested.current = false
            requestPermission()
          }}
        >
          <Text style={styles.permissionButtonText}>Autoriser</Text>
        </TouchableOpacity>
      </View>
    )
  }

  // ── Appel scan avec gestion complète de tous les codes retour ───────────────
  const doRecordScan = useCallback(
    async (
      employeeQr: string,
      siteId: number,
      currentMode: 'day' | 'night',
      options: { forceNew?: boolean } = {}
    ) => {
      if (!isMounted.current) return

      try {
        const result = await apiService.recordScan(
          employeeQr,
          siteId,
          currentMode,
          options
        )

        if (!isMounted.current) return

        if (result.status === 'success') {
          Alert.alert('✅ Succès', result.message || 'Pointage enregistré')
        } else {
          Alert.alert('⚠ Attention', result.message || 'Réponse inattendue')
        }
      } catch (error: any) {
        if (!isMounted.current) return
        Alert.alert(
          'Erreur réseau',
          error.message || 'Impossible de contacter le serveur'
        )
      } finally {
        if (isMounted.current) {
          setLoading(false)
          setHint('Placez le QR code dans le cadre')
          setTimeout(() => {
            if (isMounted.current) {
              setScanned(false)
            }
          }, 2000)
        }
      }
    },
    []
  )

  // ── Scan détecté par la caméra ──────────────────────────────────────────────
  const handleBarcodeScanned = useCallback(
    async ({ data }: { data: string }) => {
      // Vérification supplémentaire
      if (scanned || loading || !isMounted.current) return

      if (!selectedSite) {
        Alert.alert('Erreur', 'Aucun site sélectionné')
        return
      }

      setScanned(true)
      setLoading(true)
      setHint('Code détecté...')

      const employeeQr = data
      const siteId = selectedSite.id
      const currentMode = mode

      // Mode garde (nuit) → vérifier état de la garde en cours
      if (currentMode === 'night') {
        try {
          const check = await apiService.checkFirstScan(employeeQr, siteId)

          if (!isMounted.current) return

          if (check?.garde_en_cours) {
            const details = check.garde_en_cours
            const date = details?.date_pointage || 'date inconnue'
            const heure =
              details?.heure_arrivee?.substring(0, 5) || 'heure inconnue'
            const siteNom = check.site?.nom || 'site inconnu'
            const message = `Une garde a commencé le ${date} à ${heure} sur ${siteNom}.\nQue souhaitez-vous faire ?`

            setLoading(false)
            setScanned(false)
            setHint('Placez le QR code dans le cadre')

            Alert.alert('Garde en cours', message, [
              {
                text: 'Terminer cette garde',
                onPress: () => {
                  if (!isMounted.current) return
                  setScanned(true)
                  setLoading(true)
                  doRecordScan(employeeQr, siteId, currentMode)
                },
              },
              {
                text: 'Démarrer une nouvelle garde',
                onPress: () => {
                  if (!isMounted.current) return
                  setScanned(true)
                  setLoading(true)
                  doRecordScan(employeeQr, siteId, currentMode, {
                    forceNew: true,
                  })
                },
              },
              {
                text: 'Annuler',
                style: 'cancel',
              },
            ])
            return
          }
        } catch (err: any) {
          if (!isMounted.current) return
          Alert.alert(
            'Erreur',
            err.message || "Impossible de vérifier l'état des gardes"
          )
          setLoading(false)
          setScanned(false)
          setHint('Placez le QR code dans le cadre')
          return
        }
      }

      await doRecordScan(employeeQr, siteId, currentMode)
    },
    [scanned, loading, selectedSite, mode, doRecordScan]
  )

  // ── Rendu ───────────────────────────────────────────────────────────────────
  return (
    <View style={styles.container}>
      <CameraView
        style={styles.camera}
        facing="back"
        barcodeScannerSettings={{
          barcodeTypes: ['qr'],
          interval: 1000, // Réduit la fréquence de scan pour éviter les doublons
        }}
        onBarcodeScanned={
          scanned || loading ? undefined : handleBarcodeScanned
        }
        onCameraReady={() => {
          console.log('[ScanScreen] Caméra prête')
        }}
        onMountError={(error) => {
          console.error('[ScanScreen] Erreur de montage de la caméra:', error)
          Alert.alert(
            'Erreur',
            "Impossible d'initialiser la caméra. Veuillez redémarrer l'application."
          )
        }}
      />

      <View style={StyleSheet.absoluteFillObject} pointerEvents="box-none">
        {selectedSite && (
          <View style={styles.siteInfo}>
            <Ionicons
              name="location-outline"
              size={14}
              color="rgba(255,255,255,0.8)"
            />
            <Text style={styles.siteInfoText}>{selectedSite.nom}</Text>
          </View>
        )}

        <View style={styles.frameWrapper}>
          <View style={[styles.corner, styles.cornerTL]} />
          <View style={[styles.corner, styles.cornerTR]} />
          <View style={[styles.corner, styles.cornerBL]} />
          <View style={[styles.corner, styles.cornerBR]} />
          {loading && (
            <View style={styles.loadingOverlay}>
              <ActivityIndicator size="large" color={colors.white} />
            </View>
          )}
        </View>

        <Text style={styles.scanHint}>
          {loading ? 'Enregistrement...' : hint}
        </Text>

        <View style={styles.bottomContainer}>
          <View style={styles.modeToggle}>
            <TouchableOpacity
              style={[styles.modeOption, mode === 'day' && styles.modeOptionActive]}
              onPress={() => setMode('day')}
              disabled={loading}
            >
              <Ionicons
                name="sunny-outline"
                size={16}
                color={
                  mode === 'day' ? colors.ink : 'rgba(255,255,255,0.6)'
                }
              />
              <Text
                style={[
                  styles.modeOptionText,
                  mode === 'day' && styles.modeOptionTextActive,
                ]}
              >
                Jour
              </Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[
                styles.modeOption,
                mode === 'night' && styles.modeOptionActiveNight,
              ]}
              onPress={() => setMode('night')}
              disabled={loading}
            >
              <Ionicons
                name="moon-outline"
                size={16}
                color={
                  mode === 'night' ? colors.white : 'rgba(255,255,255,0.6)'
                }
              />
              <Text
                style={[
                  styles.modeOptionText,
                  mode === 'night' && styles.modeOptionTextActiveNight,
                ]}
              >
                Nuit
              </Text>
            </TouchableOpacity>
          </View>

          {scanned && !loading && (
            <TouchableOpacity
              style={styles.rescanButton}
              onPress={() => {
                setScanned(false)
                setHint('Placez le QR code dans le cadre')
              }}
            >
              <Ionicons name="refresh-outline" size={18} color={colors.white} />
              <Text style={styles.rescanText}>Scanner à nouveau</Text>
            </TouchableOpacity>
          )}
        </View>
      </View>
    </View>
  )
}

const CORNER_SIZE = 24
const CORNER_THICKNESS = 3

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#000' },
  camera: { flex: 1 },

  permissionContainer: {
    flex: 1,
    backgroundColor: colors.surface,
    justifyContent: 'center',
    alignItems: 'center',
    gap: 16,
    padding: 40,
  },
  permissionText: {
    fontSize: 16,
    color: colors.inkMuted,
    textAlign: 'center',
  },
  permissionSubText: {
    fontSize: 14,
    color: colors.inkMuted,
    textAlign: 'center',
    opacity: 0.7,
    marginHorizontal: 20,
  },
  permissionButton: {
    backgroundColor: colors.ink,
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: radius.md,
    minWidth: 160,
    alignItems: 'center',
  },
  permissionButtonText: {
    color: colors.white,
    fontWeight: '600',
    fontSize: 15,
  },

  siteInfo: {
    position: 'absolute',
    top: 60,
    alignSelf: 'center',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    backgroundColor: 'rgba(0,0,0,0.4)',
    paddingHorizontal: 14,
    paddingVertical: 7,
    borderRadius: 20,
  },
  siteInfoText: {
    color: 'rgba(255,255,255,0.9)',
    fontSize: 13,
    fontWeight: '500',
  },

  frameWrapper: {
    position: 'absolute',
    top: '28%',
    alignSelf: 'center',
    width: 240,
    height: 240,
    justifyContent: 'center',
    alignItems: 'center',
  },
  corner: {
    position: 'absolute',
    width: CORNER_SIZE,
    height: CORNER_SIZE,
    borderColor: colors.white,
  },
  cornerTL: {
    top: 0,
    left: 0,
    borderTopWidth: CORNER_THICKNESS,
    borderLeftWidth: CORNER_THICKNESS,
    borderTopLeftRadius: 4,
  },
  cornerTR: {
    top: 0,
    right: 0,
    borderTopWidth: CORNER_THICKNESS,
    borderRightWidth: CORNER_THICKNESS,
    borderTopRightRadius: 4,
  },
  cornerBL: {
    bottom: 0,
    left: 0,
    borderBottomWidth: CORNER_THICKNESS,
    borderLeftWidth: CORNER_THICKNESS,
    borderBottomLeftRadius: 4,
  },
  cornerBR: {
    bottom: 0,
    right: 0,
    borderBottomWidth: CORNER_THICKNESS,
    borderRightWidth: CORNER_THICKNESS,
    borderBottomRightRadius: 4,
  },
  loadingOverlay: {
    width: 240,
    height: 240,
    backgroundColor: 'rgba(0,0,0,0.35)',
    borderRadius: 8,
    justifyContent: 'center',
    alignItems: 'center',
  },

  scanHint: {
    position: 'absolute',
    top: '28%',
    marginTop: 254,
    alignSelf: 'center',
    color: 'rgba(255,255,255,0.7)',
    fontSize: 13,
    fontWeight: '400',
  },

  bottomContainer: {
    position: 'absolute',
    bottom: 50,
    width: '100%',
    alignItems: 'center',
    gap: 14,
  },
  modeToggle: {
    flexDirection: 'row',
    backgroundColor: 'rgba(255,255,255,0.12)',
    borderRadius: 30,
    padding: 4,
  },
  modeOption: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 8,
    paddingHorizontal: 20,
    borderRadius: 26,
    gap: 6,
  },
  modeOptionActive: {
    backgroundColor: colors.white,
  },
  modeOptionActiveNight: {
    backgroundColor: colors.amber,
  },
  modeOptionText: {
    color: 'rgba(255,255,255,0.6)',
    fontSize: 14,
    fontWeight: '500',
  },
  modeOptionTextActive: {
    color: colors.ink,
    fontWeight: '600',
  },
  modeOptionTextActiveNight: {
    color: colors.white,
    fontWeight: '600',
  },

  rescanButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: 'rgba(255,255,255,0.15)',
    paddingVertical: 10,
    paddingHorizontal: 20,
    borderRadius: 25,
  },
  rescanText: {
    color: colors.white,
    fontWeight: '500',
    fontSize: 14,
  },
})