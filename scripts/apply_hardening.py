from pathlib import Path

root = Path(__file__).resolve().parents[1]

api = root / 'mobile/ScanMobileApp/src/services/api.ts'
s = api.read_text()
if "expo-secure-store" not in s:
    s = s.replace("import AsyncStorage from '@react-native-async-storage/async-storage';", "import AsyncStorage from '@react-native-async-storage/async-storage';\nimport * as SecureStore from 'expo-secure-store';", 1)
s = s.replace("return await AsyncStorage.getItem(STORAGE_KEYS.API_TOKEN);", "return await SecureStore.getItemAsync(STORAGE_KEYS.API_TOKEN);", 1)
s = s.replace("await AsyncStorage.setItem(STORAGE_KEYS.API_TOKEN, token.trim());", "await SecureStore.setItemAsync(STORAGE_KEYS.API_TOKEN, token.trim());", 1)
s = s.replace("await AsyncStorage.multiRemove([STORAGE_KEYS.API_TOKEN, STORAGE_KEYS.CURRENT_USER]);", "await SecureStore.deleteItemAsync(STORAGE_KEYS.API_TOKEN);\n  await AsyncStorage.removeItem(STORAGE_KEYS.CURRENT_USER);", 1)
marker = "const createApi = (baseURL: string, token: string | null) => {"
helper = """let pendingQueueLock: Promise<void> = Promise.resolve();

const withPendingQueueLock = async <T>(operation: () => Promise<T>): Promise<T> => {
  const previous = pendingQueueLock;
  let release!: () => void;
  pendingQueueLock = new Promise<void>((resolve) => { release = resolve; });
  await previous;
  try { return await operation(); } finally { release(); }
};

"""
if 'let pendingQueueLock:' not in s and marker in s:
    s = s.replace(marker, helper + marker, 1)
old = """        const raw = await AsyncStorage.getItem(STORAGE_KEYS.PENDING_SCANS);
        const pending = raw ? JSON.parse(raw) : []; pending.push(payload);
        await AsyncStorage.setItem(STORAGE_KEYS.PENDING_SCANS, JSON.stringify(pending));"""
new = """        await withPendingQueueLock(async () => {
          const raw = await AsyncStorage.getItem(STORAGE_KEYS.PENDING_SCANS);
          const pending = raw ? JSON.parse(raw) : [];
          if (!pending.some((item: any) => item.client_event_id === payload.client_event_id)) {
            pending.push(payload);
            await AsyncStorage.setItem(STORAGE_KEYS.PENDING_SCANS, JSON.stringify(pending));
          }
        });"""
if old in s:
    s = s.replace(old, new, 1)
old = """    await AsyncStorage.setItem(STORAGE_KEYS.PENDING_SCANS, JSON.stringify(remaining));
    return { synced, remaining: remaining.length };"""
new = """    await withPendingQueueLock(async () => {
      const latestRaw = await AsyncStorage.getItem(STORAGE_KEYS.PENDING_SCANS);
      const latest = latestRaw ? JSON.parse(latestRaw) : [];
      const processedIds = new Set(queue.map((item: any) => item.client_event_id));
      const concurrent = Array.isArray(latest) ? latest.filter((item: any) => !processedIds.has(item.client_event_id)) : [];
      await AsyncStorage.setItem(STORAGE_KEYS.PENDING_SCANS, JSON.stringify([...remaining, ...concurrent]));
    });
    return { synced, remaining: remaining.length };"""
if old in s:
    s = s.replace(old, new, 1)
api.write_text(s)

screen = root / 'mobile/ScanMobileApp/src/screens/SiteSelectionScreen.tsx'
s = screen.read_text()
if "import { AppState } from 'react-native'" not in s:
    s = s.replace("import React, { useState, useEffect, useCallback } from 'react'", "import React, { useState, useEffect, useCallback } from 'react'\nimport { AppState } from 'react-native'", 1)
marker = """  useEffect(() => {
    initialize()
  }, [])"""
replacement = """  useEffect(() => {
    initialize()

    const subscription = AppState.addEventListener('change', (state) => {
      if (state === 'active') {
        apiService.syncPendingScans().catch(() => undefined)
      }
    })
    return () => subscription.remove()
  }, [])"""
if marker in s:
    s = s.replace(marker, replacement, 1)
screen.write_text(s)

models = root / 'pointage/models.py'
s = models.read_text()
block = """            if self.periode == 'apres_midi':
                _, fermeture_matin = self.site.get_horaires_pour_periode('matin')
                if fermeture_matin:
                    pause_duree = datetime.combine(
                        self.date_pointage, heure_ouverture
                    ) - datetime.combine(
                        self.date_pointage, fermeture_matin
                    )
                    if pause_duree > timedelta(0):
                        retard_brut = retard_brut

"""
models.write_text(s.replace(block, ''))
