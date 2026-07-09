// src/navigation/AppNavigator.tsx

import React from 'react'
import { createStackNavigator } from '@react-navigation/stack'
import { NavigationContainer } from '@react-navigation/native'

// 🔥 IMPORT DES SCREENS
import HomeScreen from '../screens/HomeScreen'
import ScanScreen from '../screens/ScanScreen'
import SiteSelectionScreen from '../screens/SiteSelectionScreen'
import HistoryScreen from '../screens/HistoryScreen'
import ConfigScreen from '../screens/ConfigScreen'

const Stack = createStackNavigator()

const AppNavigator = () => {
  return (
    <NavigationContainer>
      <Stack.Navigator
        initialRouteName="Home"
        screenOptions={{
          headerStyle: { backgroundColor: '#007AFF' },
          headerTintColor: '#fff',
          headerTitleStyle: { fontWeight: 'bold' },
        }}
      >
        <Stack.Screen
          name="Home"
          component={HomeScreen}
          options={{ title: 'Accueil' }}
        />
        <Stack.Screen
          name="Scan"
          component={ScanScreen}
          options={{ title: 'Scanner' }}
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