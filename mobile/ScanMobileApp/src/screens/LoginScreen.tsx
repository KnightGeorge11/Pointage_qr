import React, { useState } from 'react'
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  ActivityIndicator, KeyboardAvoidingView, Platform,
} from 'react-native'
import { useAppContext } from '../context/AppContext'
import { colors, radius } from '../theme/colors'

const LoginScreen = ({ navigation }: any) => {
  const { login } = useAppContext()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleLogin = async () => {
    if (!username.trim() || !password) {
      setError('Identifiant et mot de passe requis.')
      return
    }
    setLoading(true)
    setError(null)
    try {
      // login() ne fait qu'authentifier l'OPÉRATEUR de l'application.
      // L'employé pointé sera identifié séparément via son QR, lors du scan.
      await login(username.trim(), password)
    } catch (err: any) {
      const status = err?.response?.status
      if (status === 401) {
        setError("Identifiant ou mot de passe incorrect.")
      } else if (status === 403) {
        setError('Ce compte est désactivé.')
      } else if (!err?.response) {
        setError('Impossible de joindre le serveur. Vérifiez la connexion.')
      } else {
        setError(err?.response?.data?.message || 'Erreur de connexion.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <View style={styles.card}>
        <Text style={styles.title}>Pointage QR</Text>
        <Text style={styles.subtitle}>Connexion opérateur</Text>

        {error && (
          <View style={styles.errorBox}>
            <Text style={styles.errorText}>{error}</Text>
          </View>
        )}

        <Text style={styles.label}>Identifiant</Text>
        <TextInput
          style={styles.input}
          value={username}
          onChangeText={setUsername}
          placeholder="jean.dupont"
          autoCapitalize="none"
          autoCorrect={false}
          editable={!loading}
        />

        <Text style={styles.label}>Mot de passe</Text>
        <TextInput
          style={styles.input}
          value={password}
          onChangeText={setPassword}
          placeholder="••••••••"
          secureTextEntry
          autoCapitalize="none"
          editable={!loading}
          onSubmitEditing={handleLogin}
        />

        <TouchableOpacity
          style={[styles.button, loading && styles.buttonDisabled]}
          onPress={handleLogin}
          disabled={loading}
        >
          {loading ? (
            <ActivityIndicator color={colors.white} />
          ) : (
            <Text style={styles.buttonText}>Se connecter</Text>
          )}
        </TouchableOpacity>

        <Text style={styles.hint}>
          Utilisez votre compte utilisateur habituel — ce compte identifie
          uniquement l'opérateur de l'application, pas les employés scannés.
        </Text>

        <TouchableOpacity
          style={styles.settingsLink}
          onPress={() => navigation.navigate('Config')}
        >
          <Text style={styles.settingsLinkText}>⚙ Paramètres serveur</Text>
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  )
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.surface,
    justifyContent: 'center',
    padding: 24,
  },
  card: {
    backgroundColor: colors.white,
    borderRadius: radius.lg,
    padding: 28,
    borderWidth: 1,
    borderColor: colors.line,
  },
  title: {
    fontSize: 24,
    fontWeight: '700',
    color: colors.ink,
    textAlign: 'center',
  },
  subtitle: {
    fontSize: 14,
    color: colors.inkMuted,
    textAlign: 'center',
    marginTop: 4,
    marginBottom: 24,
  },
  label: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.inkMuted,
    marginBottom: 6,
    marginTop: 12,
  },
  input: {
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.sm,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 15,
    color: colors.ink,
    backgroundColor: colors.surface,
  },
  button: {
    backgroundColor: colors.blue,
    borderRadius: radius.sm,
    paddingVertical: 14,
    alignItems: 'center',
    marginTop: 24,
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  buttonText: {
    color: colors.white,
    fontWeight: '700',
    fontSize: 15,
  },
  errorBox: {
    backgroundColor: colors.redDim,
    borderRadius: radius.sm,
    padding: 12,
    marginBottom: 8,
  },
  errorText: {
    color: colors.redText,
    fontSize: 13,
  },
  hint: {
    fontSize: 11,
    color: colors.inkMuted,
    textAlign: 'center',
    marginTop: 20,
    lineHeight: 16,
  },
  settingsLink: {
    marginTop: 16,
    alignItems: 'center',
  },
  settingsLinkText: {
    fontSize: 13,
    color: colors.inkMuted,
    fontWeight: '600',
  },
})

export default LoginScreen
