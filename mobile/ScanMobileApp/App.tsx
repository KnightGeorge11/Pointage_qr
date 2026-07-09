// App.tsx
import React from 'react'
import { View, Text, ActivityIndicator, StyleSheet } from 'react-native'
import { Ionicons } from '@expo/vector-icons'

import { AppProvider } from './src/context/AppContext'
import AppNavigator from './src/navigation/AppNavigator'

const COLORS = {
  primary: '#007AFF',
  card: '#FFFFFF',
  text: '#333333'
}

export default function App() {
  return (
    <AppProvider>
      <AppNavigator />
    </AppProvider>
  )
}

const styles = StyleSheet.create({
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: COLORS.card
  },
  loadingText: {
    marginTop: 20,
    fontSize: 18,
    color: COLORS.text
  }
})