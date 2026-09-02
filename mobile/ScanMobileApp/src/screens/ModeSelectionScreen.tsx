// screens/ModeSelectionScreen.tsx
import React, { useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Alert, ActivityIndicator, SafeAreaView } from 'react-native';
import { useNavigation, useRoute } from '@react-navigation/native';
import { apiService } from '../services/api';
import { Ionicons } from '@expo/vector-icons';

const ModeSelectionScreen = () => {
  const [loading, setLoading] = useState(false);
  const navigation = useNavigation();
  const route = useRoute();
  const { employeeQr, siteId, scanInfo } = route.params as any;

  const handleSelect = async (mode: 'normal' | 'garde') => {
    setLoading(true);
    try {
      const apiMode: 'day' | 'night' = mode === 'garde' ? 'night' : 'day';
      const forceNew = mode === 'garde' ? Boolean(scanInfo.garde_planifiee) : Boolean(scanInfo.first_scan);
      const result = await apiService.recordScan(employeeQr, siteId, apiMode, { forceNew });
      Alert.alert('Succès', result.message || 'Pointage enregistré', [
        { text: 'OK', onPress: () => navigation.navigate('Scan' as never) },
      ]);
    } catch (error: any) {
      Alert.alert('Erreur', error.message || 'Erreur lors de l’enregistrement');
    } finally {
      setLoading(false);
    }
  };

  const employeeName = scanInfo.employe?.nom_complet || employeeQr;
  const hasGardeAlert = Boolean(scanInfo.garde_planifiee || scanInfo.garde_en_cours);

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Mode de pointage</Text>
        <View style={styles.employeeRow}>
          <Ionicons name="person-circle-outline" size={18} color="#888" />
          <Text style={styles.employeeName}>{employeeName}</Text>
        </View>
      </View>
      {hasGardeAlert && (
        <View style={styles.alertBanner}>
          <Ionicons name="information-circle-outline" size={18} color="#92400E" />
          <Text style={styles.alertText}>
            {scanInfo.garde_en_cours
              ? 'Une garde est en cours — sélectionnez Garde pour la terminer.'
              : 'Une garde est planifiée — sélectionnez Garde pour démarrer.'}
          </Text>
        </View>
      )}
      <View style={styles.cardsContainer}>
        <TouchableOpacity style={[styles.card, loading && styles.cardDisabled]} onPress={() => handleSelect('normal')} disabled={loading} activeOpacity={0.7}>
          <View style={[styles.iconWrapper, { backgroundColor: '#f0f0f0' }]}><Ionicons name="time-outline" size={32} color="#1a1a1a" /></View>
          <View style={styles.cardContent}><Text style={styles.cardTitle}>Normal</Text><Text style={styles.cardDesc}>Pointage standard · matin / après-midi</Text></View>
          <Ionicons name="chevron-forward" size={20} color="#ccc" />
        </TouchableOpacity>
        <TouchableOpacity style={[styles.card, styles.gardeCard, loading && styles.cardDisabled]} onPress={() => handleSelect('garde')} disabled={loading} activeOpacity={0.7}>
          <View style={[styles.iconWrapper, { backgroundColor: '#FEF3C7' }]}><Ionicons name="shield-checkmark-outline" size={32} color="#D97706" /></View>
          <View style={styles.cardContent}><Text style={styles.cardTitle}>Garde de nuit</Text><Text style={styles.cardDesc}>Service de garde · période nuit</Text></View>
          <Ionicons name="chevron-forward" size={20} color="#ccc" />
        </TouchableOpacity>
      </View>
      {loading && <View style={styles.loadingOverlay}><ActivityIndicator size="large" color="#1a1a1a" /><Text style={styles.loadingText}>Enregistrement...</Text></View>}
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f5f5f7' },
  header: { paddingHorizontal: 20, paddingTop: 16, paddingBottom: 20 },
  title: { fontSize: 28, fontWeight: '700', color: '#1a1a1a', marginBottom: 8 },
  employeeRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  employeeName: { fontSize: 15, color: '#888', fontWeight: '500' },
  alertBanner: { flexDirection: 'row', alignItems: 'flex-start', marginHorizontal: 20, marginBottom: 20, padding: 14, backgroundColor: '#FEF3C7', borderRadius: 12, gap: 10 },
  alertText: { flex: 1, fontSize: 13, color: '#92400E', lineHeight: 18 },
  cardsContainer: { paddingHorizontal: 20, gap: 12 },
  card: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#fff', borderRadius: 14, padding: 16, shadowColor: '#000', shadowOpacity: 0.04, shadowOffset: { width: 0, height: 2 }, shadowRadius: 6, elevation: 2, gap: 14 },
  gardeCard: { borderWidth: 1.5, borderColor: '#FDE68A' },
  cardDisabled: { opacity: 0.5 },
  iconWrapper: { width: 56, height: 56, borderRadius: 14, justifyContent: 'center', alignItems: 'center' },
  cardContent: { flex: 1 },
  cardTitle: { fontSize: 17, fontWeight: '600', color: '#1a1a1a', marginBottom: 3 },
  cardDesc: { fontSize: 13, color: '#aaa' },
  loadingOverlay: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(255,255,255,0.8)', justifyContent: 'center', alignItems: 'center', gap: 12 },
  loadingText: { fontSize: 15, color: '#555', fontWeight: '500' },
});

export default ModeSelectionScreen;
