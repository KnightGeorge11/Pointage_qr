// App.tsx
import React from 'react'
// Import GestureHandler MUST BE BEFORE navigation (React Navigation dependency)
import 'react-native-gesture-handler'

import { AppProvider } from './src/context/AppContext'
import AppNavigator from './src/navigation/AppNavigator'

export default function App() {
  return (
    <AppProvider>
      <AppNavigator />
    </AppProvider>
  )
}
