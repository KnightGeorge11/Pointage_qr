import React, { useState, useEffect } from 'react'
import { View, Text, TextInput, TouchableOpacity, StyleSheet, Alert, ActivityIndicator } from 'react-native'
import { useAppContext } from '../context/AppContext'
import { testConnection, setBaseUrl, getCurrentServerUrl } from '../services/api'
import { colors, radius } from '../theme/colors'

const ConfigScreen = () => {
  const { apiStatus, setApiStatus, currentUser, logout } = useAppContext()
  const [baseUrl, setBaseUrlState] = useState(apiStatus.baseUrl || getCurrentServerUrl())
  const [isSaving, setIsSaving] = useState(false)
  const [isTesting, setIsTesting] = useState(false)
  const [isLoggingOut, setIsLoggingOut] = useState(false)
  const [testResult, setTestResult] = useState<string | null>(null)

  useEffect(() => {
    setBaseUrlState(apiStatus.baseUrl || getCurrentServerUrl())
  }, [apiStatus])

  const handleSave = async () => {
    setIsSaving(true)
    try {
      await setBaseUrl(baseUrl)
      const status = await testConnection()
      setApiStatus({
        connected: status.success,
        baseUrl: baseUrl,
        lastCheck: new Date(),
      })
      Alert.alert('Succès', 'Configuration enregistrée.')
    } catch (error) {
      Alert.alert('Erreur', 'Impossible de sauvegarder la configuration.')
    } finally {
      setIsSaving(false)
    }
  }

  const handleTestConnection = async () => {
    setIsTesting(true)
    setTestResult(null)
    try {
      // Teste l'URL actuellement saisie dans le champ, pas forcément
      // celle déjà enregistrée — sinon "Tester" avant "Sauvegarder"
      // testerait silencieusement l'ancienne configuration.
      const status = await testConnection(baseUrl)
      setTestResult(status.success ? 'Connexion réussie' : 'Connexion échouée')
    } catch (error) {
      setTestResult('Erreur lors du test')
    } finally {
      setIsTesting(false)
    }
  }

  const handleLogout = () => {
    Alert.alert(
      'Déconnexion',
      'Voulez-vous vraiment vous déconnecter ?',
      [
        { text: 'Annuler', style: 'cancel' },
        {
          text: 'Se déconnecter',
          style: 'destructive',
          onPress: async () => {
            setIsLoggingOut(true)
            try {
              // Révoque le jeton côté serveur ET purge le stockage local
              // (voir apiService.logout) — le navigateur bascule ensuite
              // automatiquement sur l'écran Login (AppNavigator réagit à
              // isAuthenticated).
              await logout()
            } finally {
              setIsLoggingOut(false)
            }
          },
        },
      ]
    )
  }

  return (
    <View style={styles.container}>
      {currentUser && (
        <View style={styles.userCard}>
          <Text style={styles.userCardLabel}>Connecté en tant que</Text>
          <Text style={styles.userCardName}>
            {currentUser.first_name || currentUser.last_name
              ? `${currentUser.first_name} ${currentUser.last_name}`.trim()
              : currentUser.username}
          </Text>
          <Text style={styles.userCardUsername}>@{currentUser.username}</Text>
        </View>
      )}

      <Text style={styles.label}>URL de l'API :</Text>
      <TextInput
        style={styles.input}
        value={baseUrl}
        onChangeText={setBaseUrlState}
        placeholder="http://pointageqr.local:8000"
        autoCapitalize="none"
        autoCorrect={false}
      />

      <TouchableOpacity style={styles.button} onPress={handleSave} disabled={isSaving}>
        {isSaving ? <ActivityIndicator color={colors.white} /> : <Text style={styles.buttonText}>Sauvegarder</Text>}
      </TouchableOpacity>

      <TouchableOpacity
        style={[styles.button, { backgroundColor: colors.green }]}
        onPress={handleTestConnection}
        disabled={isTesting}
      >
        {isTesting ? <ActivityIndicator color={colors.white} /> : <Text style={styles.buttonText}>Tester la connexion</Text>}
      </TouchableOpacity>

      {testResult && (
        <Text style={[styles.resultText, { color: testResult.includes('réussie') ? colors.greenText : colors.redText }]}>
          {testResult}
        </Text>
      )}

      {currentUser && (
        <TouchableOpacity
          style={[styles.button, styles.logoutButton]}
          onPress={handleLogout}
          disabled={isLoggingOut}
        >
          {isLoggingOut ? <ActivityIndicator color={colors.white} /> : <Text style={styles.buttonText}>Se déconnecter</Text>}
        </TouchableOpacity>
      )}
    </View>
  )
}

export default ConfigScreen

const styles = StyleSheet.create({
  container: { flex: 1, padding: 20, backgroundColor: colors.surface },
  label: { fontSize: 16, fontWeight: '600', marginTop: 15, marginBottom: 5, color: colors.ink },
  input: {
    backgroundColor: colors.white, borderRadius: radius.md, paddingVertical: 12, paddingHorizontal: 15,
    fontSize: 16, marginBottom: 10, borderWidth: 1, borderColor: colors.line,
  },
  button: {
    backgroundColor: colors.ink, borderRadius: radius.md, paddingVertical: 15,
    alignItems: 'center', marginTop: 15,
  },
  buttonText: { color: colors.white, fontSize: 16, fontWeight: '600' },
  resultText: { marginTop: 20, fontSize: 16, fontWeight: '500', textAlign: 'center' },
  userCard: {
    backgroundColor: colors.white, borderRadius: radius.md, padding: 16,
    borderWidth: 1, borderColor: colors.line, marginBottom: 10,
  },
  userCardLabel: { fontSize: 11, color: colors.inkMuted, textTransform: 'uppercase', fontWeight: '600' },
  userCardName: { fontSize: 18, fontWeight: '700', color: colors.ink, marginTop: 4 },
  userCardUsername: { fontSize: 13, color: colors.inkMuted, marginTop: 2 },
  logoutButton: { backgroundColor: colors.redText, marginTop: 30 },
})
