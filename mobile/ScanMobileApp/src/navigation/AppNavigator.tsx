// src/navigation/AppNavigator.tsx

import React from 'react'
import { View, ActivityIndicator } from 'react-native'
import { createNativeStackNavigator } from '@react-navigation/native-stack'
import { NavigationContainer } from '@react-navigation/native'

// 🔥 IMPORT DES SCREENS
import LoginScreen from '../screens/LoginScreen'
import HomeScreen from '../screens/HomeScreen'
import ScanScreen from '../screens/ScanScreen'
import SiteSelectionScreen from '../screens/SiteSelectionScreen'
import HistoryScreen from '../screens/HistoryScreen'
import ConfigScreen from '../screens/ConfigScreen'
import { useAppContext } from '../context/AppContext'
import { colors } from '../theme/colors'

const Stack = createNativeStackNavigator()

const AppNavigator = () => {
  const { isAuthenticated, authChecked } = useAppContext()

  // Le temps de vérifier s'il existe déjà un jeton valide en stockage
  // local : on ne montre jamais l'écran Login "en clignotant" si
  // l'utilisateur est déjà connecté.
  if (!authChecked) {
    return (
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.surface }}>
        <ActivityIndicator size="large" color={colors.blue} />
      </View>
    )
  }

  return (
    <NavigationContainer>
      <Stack.Navigator
        initialRouteName={isAuthenticated ? 'Home' : 'Login'}
        screenOptions={{
          headerStyle: { backgroundColor: colors.white },
          headerShadowVisible: false,
          headerTintColor: colors.ink,
          headerTitleStyle: { fontWeight: 'bold' },
        }}
      >
        {!isAuthenticated ? (
          <Stack.Screen
            name="Login"
            component={LoginScreen}
            options={{ headerShown: false }}
          />
        ) : (
          <>
            <Stack.Screen
              name="Home"
              component={HomeScreen}
              options={{ title: 'Accueil' }}
            />
            <Stack.Screen
              name="Scan"
              component={ScanScreen}
              options={{
                title: 'Scanner',
                headerStyle: { backgroundColor: colors.ink },
                headerShadowVisible: false,
                headerTintColor: colors.white,
              }}
            />
            <Stack.Screen
              name="SiteSelectionScreen"
              component={SiteSelectionScreen}
              options={{ title: 'Sélection du site' }}
            />
            <Stack.Screen
              name="History"
              component={HistoryScreen}
              options={{ title: 'Historique' }}
            />
          </>
        )}
        {/* 'Config' est enregistré en dehors du bloc isAuthenticated : il
            doit rester joignable AVANT connexion. Si le serveur configuré
            est injoignable, l'utilisateur ne peut jamais se connecter — sans
            cet accès, il n'aurait alors aucun moyen de corriger l'URL une
            fois l'app installée (voir bouton "Paramètres serveur" sur
            LoginScreen). */}
        <Stack.Screen
          name="Config"
          component={ConfigScreen}
          options={{ title: 'Configuration' }}
        />
      </Stack.Navigator>
    </NavigationContainer>
  )
}

export default AppNavigator