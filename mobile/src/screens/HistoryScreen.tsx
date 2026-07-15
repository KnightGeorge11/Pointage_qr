// screens/HistoryScreen.tsx
//
// Journal du jour — tous les pointages de la journée tirés du serveur.
// Endpoint : GET /api/mobile/pointages/today/?site_id=N&date=YYYY-MM-DD
//
// Affichage par ligne :
//   - Nom Prénom de l'employé
//   - Heure arrivée → heure départ
//   - Badge période (Matin / Après-midi / Nuit)
//   - Statut de présence (En cours / Parti)
// Navigation entre dates, filtre par site, auto-refresh 30s, pull-to-refresh.

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, ScrollView,
  RefreshControl, ActivityIndicator, SafeAreaView,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppContext } from '../context/AppContext';
import { apiService, TodayPointage } from '../services/api';

const REFRESH_INTERVAL_MS = 30_000;

const PERIODE_CONFIG: Record<string, { label: string; color: string; icon: any }> = {
  matin:      { label: 'Matin',      color: '#F59E0B', icon: 'sunny-outline' },
  apres_midi: { label: 'Après-midi', color: '#3B82F6', icon: 'partly-sunny-outline' },
  nuit:       { label: 'Nuit',       color: '#7C3AED', icon: 'moon-outline' },
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtHeure(t?: string): string {
  return t ? t.substring(0, 5) : '—';
}

function getDateLabel(d: Date): string {
  const today     = new Date(); today.setHours(0, 0, 0, 0);
  const yesterday = new Date(today); yesterday.setDate(today.getDate() - 1);
  const target    = new Date(d);    target.setHours(0, 0, 0, 0);
  if (target.getTime() === today.getTime())     return "Aujourd'hui";
  if (target.getTime() === yesterday.getTime()) return 'Hier';
  return d.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

function toISODate(d: Date): string {
  return d.toISOString().split('T')[0];
}

function isToday(d: Date): boolean {
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const t = new Date(d);   t.setHours(0, 0, 0, 0);
  return t.getTime() === today.getTime();
}

// ── Carte pointage ────────────────────────────────────────────────────────────

const PointageCard = ({ item, showSite }: { item: TodayPointage; showSite: boolean }) => {
  const cfg = PERIODE_CONFIG[item.periode] ?? { label: item.periode, color: '#888', icon: 'time-outline' };
  const enCours = !!item.heure_arrivee && !item.heure_depart;
  const parti   = !!item.heure_arrivee && !!item.heure_depart;

  return (
    <View style={styles.card}>
      {/* Ligne 1 : Nom + badge statut */}
      <View style={styles.cardTop}>
        <Text style={styles.empNom} numberOfLines={1}>{item.employe_nom}</Text>
        <View style={[styles.statusBadge, { backgroundColor: enCours ? '#DCFCE7' : parti ? '#F3F4F6' : '#FEE2E2' }]}>
          <View style={[styles.statusDot, { backgroundColor: enCours ? '#16A34A' : parti ? '#9CA3AF' : '#EF4444' }]} />
          <Text style={[styles.statusText, { color: enCours ? '#15803D' : parti ? '#6B7280' : '#DC2626' }]}>
            {enCours ? 'En cours' : parti ? 'Parti' : 'Absent'}
          </Text>
        </View>
      </View>

      {/* Ligne 2 : Poste (optionnel) */}
      {item.employe_poste ? (
        <Text style={styles.empPoste}>{item.employe_poste}</Text>
      ) : null}

      {/* Ligne 3 : Heures + badge période */}
      <View style={styles.cardMiddle}>
        <Text style={styles.heures}>
          {fmtHeure(item.heure_arrivee)}
          <Text style={styles.arrow}>  →  </Text>
          {fmtHeure(item.heure_depart)}
        </Text>

        <View style={[styles.periodeBadge, { backgroundColor: cfg.color + '22' }]}>
          <Ionicons name={cfg.icon} size={12} color={cfg.color} />
          <Text style={[styles.periodeText, { color: cfg.color }]}>{cfg.label}</Text>
        </View>

        {item.type_journee === 'garde' && (
          <View style={styles.gardeBadge}>
            <Text style={styles.gardeText}>Garde</Text>
          </View>
        )}
      </View>

      {/* Ligne 4 : Site (si vue "tous sites") + retard */}
      {(showSite || (item.retard && item.retard !== '0:00:00')) && (
        <View style={styles.cardBottom}>
          {showSite && item.site ? (
            <View style={styles.siteRow}>
              <Ionicons name="location-outline" size={12} color="#bbb" />
              <Text style={styles.siteName}>{item.site}</Text>
            </View>
          ) : <View />}
          {item.retard && item.retard !== '0:00:00' && (
            <View style={styles.retardRow}>
              <Ionicons name="alert-circle" size={12} color="#EF4444" />
              <Text style={styles.retardText}>Retard</Text>
            </View>
          )}
        </View>
      )}
    </View>
  );
};

// ── Écran principal ───────────────────────────────────────────────────────────

const HistoryScreen = ({ navigation }: any) => {
  const { selectedSite, sites, setSites } = useAppContext();

  const [date, setDate]           = useState(new Date());
  const [siteId, setSiteId]       = useState<number | null>(selectedSite?.id ?? null);
  const [data, setData]           = useState<TodayPointage[]>([]);
  const [loading, setLoading]     = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError]         = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [showSitePicker, setShowSitePicker] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Chargement ─────────────────────────────────────────────────────
  const fetchData = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    setError(null);
    try {
      const result = await apiService.getTodayPointages(siteId, toISODate(date));
      setData(result.data ?? []);
      setLastRefresh(new Date());
    } catch (err: any) {
      setError(err.message || 'Erreur de chargement');
      if (!silent) setData([]);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [siteId, date]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Si la liste globale des sites n'a pas encore été chargée (ex : l'utilisateur
  // arrive directement sur cet écran sans être passé par la sélection de site),
  // on la charge nous-mêmes pour que le filtre par site fonctionne quand même.
  useEffect(() => {
    if (!sites || sites.length === 0) {
      apiService.getSites().then(setSites).catch(() => {});
    }
  }, []);

  // Auto-refresh uniquement si on affiche aujourd'hui
  useEffect(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    if (isToday(date)) {
      timerRef.current = setInterval(() => fetchData(true), REFRESH_INTERVAL_MS);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [fetchData, date]);

  const onRefresh = useCallback(() => { setRefreshing(true); fetchData(); }, [fetchData]);

  // ── Navigation dates ────────────────────────────────────────────────
  const prevDay = () => {
    const d = new Date(date); d.setDate(d.getDate() - 1); setDate(d);
  };
  const nextDay = () => {
    if (!isToday(date)) { const d = new Date(date); d.setDate(d.getDate() + 1); setDate(d); }
  };
  const goToday = () => setDate(new Date());

  // ── Stats résumées ──────────────────────────────────────────────────
  const nbPresents = data.filter(p => p.heure_arrivee && !p.heure_depart).length;
  const nbPartis   = data.filter(p => p.heure_arrivee && p.heure_depart).length;

  // Site affiché dans le filtre
  const siteLabel = siteId
    ? (sites?.find(s => s.id === siteId)?.nom ?? `Site ${siteId}`)
    : 'Tous les sites';

  // ── Rendu ───────────────────────────────────────────────────────────
  return (
    <SafeAreaView style={styles.container}>

      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.title}>Journal du jour</Text>
        {lastRefresh && (
          <Text style={styles.refreshHint}>
            {isToday(date) ? `⟳ ${lastRefresh.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}` : ''}
          </Text>
        )}
      </View>

      {/* Barre de filtres */}
      <View style={styles.filtersBar}>
        {/* Navigation date */}
        <View style={styles.dateNav}>
          <TouchableOpacity onPress={prevDay} style={styles.navArrow}>
            <Ionicons name="chevron-back" size={18} color="#555" />
          </TouchableOpacity>
          <TouchableOpacity onPress={goToday} style={styles.dateBtn}>
            <Text style={styles.dateBtnText}>{getDateLabel(date)}</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={nextDay} style={[styles.navArrow, isToday(date) && styles.navArrowDisabled]}>
            <Ionicons name="chevron-forward" size={18} color={isToday(date) ? '#ccc' : '#555'} />
          </TouchableOpacity>
        </View>

        {/* Sélecteur de site */}
        <TouchableOpacity style={styles.siteBtn} onPress={() => setShowSitePicker(v => !v)}>
          <Ionicons name="location-outline" size={13} color="#555" />
          <Text style={styles.siteBtnText} numberOfLines={1}>{siteLabel}</Text>
          <Ionicons name={showSitePicker ? 'chevron-up' : 'chevron-down'} size={13} color="#555" />
        </TouchableOpacity>
      </View>

      {/* Dropdown site picker */}
      {showSitePicker && (
        <View style={styles.sitePicker}>
          <TouchableOpacity
            style={[styles.sitePickerItem, !siteId && styles.sitePickerItemActive]}
            onPress={() => { setSiteId(null); setShowSitePicker(false); }}
          >
            <Text style={[styles.sitePickerText, !siteId && styles.sitePickerTextActive]}>
              Tous les sites
            </Text>
            {!siteId && <Ionicons name="checkmark" size={16} color="#007AFF" />}
          </TouchableOpacity>
          {(sites ?? []).map(s => (
            <TouchableOpacity
              key={s.id}
              style={[styles.sitePickerItem, siteId === s.id && styles.sitePickerItemActive]}
              onPress={() => { setSiteId(s.id); setShowSitePicker(false); }}
            >
              <Text style={[styles.sitePickerText, siteId === s.id && styles.sitePickerTextActive]}>
                {s.nom}
              </Text>
              {siteId === s.id && <Ionicons name="checkmark" size={16} color="#007AFF" />}
            </TouchableOpacity>
          ))}
        </View>
      )}

      {/* Compteurs résumés */}
      {!loading && data.length > 0 && (
        <View style={styles.statsRow}>
          <Text style={styles.statsText}>
            {data.length} pointage{data.length !== 1 ? 's' : ''}
          </Text>
          <Text style={styles.statsDot}>·</Text>
          <View style={styles.statsItem}>
            <View style={[styles.statusDot, { backgroundColor: '#16A34A' }]} />
            <Text style={styles.statsText}>{nbPresents} présent{nbPresents !== 1 ? 's' : ''}</Text>
          </View>
          <Text style={styles.statsDot}>·</Text>
          <View style={styles.statsItem}>
            <View style={[styles.statusDot, { backgroundColor: '#9CA3AF' }]} />
            <Text style={styles.statsText}>{nbPartis} parti{nbPartis !== 1 ? 's' : ''}</Text>
          </View>
        </View>
      )}

      {/* Contenu */}
      {loading && !refreshing ? (
        <View style={styles.center}>
          <ActivityIndicator size="large" color="#1a1a1a" />
        </View>
      ) : error ? (
        <View style={styles.center}>
          <Ionicons name="alert-circle-outline" size={48} color="#ccc" />
          <Text style={styles.errorText}>{error}</Text>
          <TouchableOpacity style={styles.retryBtn} onPress={() => fetchData()}>
            <Text style={styles.retryText}>Réessayer</Text>
          </TouchableOpacity>
        </View>
      ) : data.length === 0 ? (
        <View style={styles.center}>
          <Ionicons name="calendar-outline" size={48} color="#ddd" />
          <Text style={styles.emptyText}>Aucun pointage pour cette journée</Text>
        </View>
      ) : (
        <ScrollView
          contentContainerStyle={styles.list}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#1a1a1a" />
          }
        >
          {data.map(item => (
            <PointageCard key={item.id} item={item} showSite={!siteId} />
          ))}
        </ScrollView>
      )}
    </SafeAreaView>
  );
};

export default HistoryScreen;

// ── Styles ────────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  container:   { flex: 1, backgroundColor: '#f5f5f7' },

  header: {
    paddingHorizontal: 20, paddingTop: 16, paddingBottom: 4,
    flexDirection: 'row', alignItems: 'baseline', justifyContent: 'space-between',
  },
  title:       { fontSize: 26, fontWeight: '700', color: '#1a1a1a' },
  refreshHint: { fontSize: 11, color: '#bbb', fontWeight: '400' },

  // Filtres
  filtersBar: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 20, paddingVertical: 10, gap: 10,
  },
  dateNav:  { flexDirection: 'row', alignItems: 'center', gap: 4 },
  navArrow: { padding: 6 },
  navArrowDisabled: { opacity: 0.3 },
  dateBtn: {
    backgroundColor: '#fff', borderRadius: 10,
    paddingHorizontal: 14, paddingVertical: 7,
    shadowColor: '#000', shadowOpacity: 0.04, shadowOffset: { width: 0, height: 1 }, shadowRadius: 4, elevation: 1,
  },
  dateBtnText: { fontSize: 14, fontWeight: '600', color: '#1a1a1a' },

  siteBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    backgroundColor: '#fff', borderRadius: 10,
    paddingHorizontal: 12, paddingVertical: 7, flex: 1,
    shadowColor: '#000', shadowOpacity: 0.04, shadowOffset: { width: 0, height: 1 }, shadowRadius: 4, elevation: 1,
  },
  siteBtnText: { flex: 1, fontSize: 13, color: '#555', fontWeight: '500' },

  // Dropdown site
  sitePicker: {
    marginHorizontal: 20, backgroundColor: '#fff', borderRadius: 12,
    shadowColor: '#000', shadowOpacity: 0.08, shadowOffset: { width: 0, height: 4 }, shadowRadius: 12, elevation: 4,
    marginBottom: 4, zIndex: 100,
  },
  sitePickerItem: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 16, paddingVertical: 13,
    borderBottomWidth: 1, borderBottomColor: '#f0f0f0',
  },
  sitePickerItemActive: { backgroundColor: '#F0F7FF' },
  sitePickerText:       { fontSize: 14, color: '#333' },
  sitePickerTextActive: { color: '#007AFF', fontWeight: '600' },

  // Stats
  statsRow: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 20, paddingBottom: 8,
  },
  statsItem: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  statsText: { fontSize: 12, color: '#888', fontWeight: '500' },
  statsDot:  { fontSize: 12, color: '#ccc' },

  // Contenu
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', gap: 12, padding: 40 },
  errorText: { fontSize: 14, color: '#EF4444', textAlign: 'center' },
  emptyText: { fontSize: 14, color: '#bbb', textAlign: 'center' },
  retryBtn:  { backgroundColor: '#1a1a1a', paddingHorizontal: 20, paddingVertical: 10, borderRadius: 20 },
  retryText: { color: '#fff', fontWeight: '600' },
  list:      { paddingHorizontal: 16, paddingTop: 4, paddingBottom: 30, gap: 8 },

  // Carte
  card: {
    backgroundColor: '#fff', borderRadius: 14, padding: 14,
    shadowColor: '#000', shadowOpacity: 0.04, shadowOffset: { width: 0, height: 2 }, shadowRadius: 6, elevation: 2,
  },
  cardTop:  { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 2 },
  empNom:   { fontSize: 15, fontWeight: '700', color: '#1a1a1a', flex: 1, marginRight: 8 },
  empPoste: { fontSize: 12, color: '#aaa', marginBottom: 8 },

  statusBadge: { flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 20 },
  statusDot:   { width: 7, height: 7, borderRadius: 4 },
  statusText:  { fontSize: 12, fontWeight: '600' },

  cardMiddle: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 6 },
  heures:     { fontSize: 17, fontWeight: '700', color: '#1a1a1a' },
  arrow:      { fontSize: 14, color: '#bbb', fontWeight: '400' },

  periodeBadge: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 20 },
  periodeText:  { fontSize: 11, fontWeight: '600' },

  gardeBadge: { backgroundColor: '#FEF3C7', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 20 },
  gardeText:  { fontSize: 11, fontWeight: '600', color: '#D97706' },

  cardBottom: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 8 },
  siteRow:    { flexDirection: 'row', alignItems: 'center', gap: 4 },
  siteName:   { fontSize: 12, color: '#bbb' },
  retardRow:  { flexDirection: 'row', alignItems: 'center', gap: 4 },
  retardText: { fontSize: 12, color: '#EF4444', fontWeight: '600' },
});
