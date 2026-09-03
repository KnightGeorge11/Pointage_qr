// theme/colors.ts
//
// Source de vérité visuelle de l'application mobile.
// Les tokens sémantiques sont alignés sur le Design System Web Pointage QR
// (pointage/templates/pointage/base.html). Les écrans ne doivent pas écrire
// de couleurs arbitraires : ils importent toujours ce fichier.

export const colors = {
  // Neutres
  ink:        '#0F172A',
  inkSoft:    '#334155',
  inkMuted:   '#64748B',

  // Fonds
  surface:    '#F8FAFC',
  surfaceAlt: '#F1F5F9',
  white:      '#FFFFFF',

  // Bordures
  line:       '#E2E8F0',
  lineSoft:   '#F1F5F9',

  // Succès
  green:      '#22C55E',
  greenDim:   '#F0FDF4',
  greenText:  '#15803D',

  // Avertissement / garde de nuit
  amber:      '#F59E0B',
  amberDim:   '#FFFBEB',
  amberText:  '#D97706',

  // Nuit — même famille neutre, sans violet arbitraire.
  night:      '#334155',
  nightDim:   '#F1F5F9',
  nightText:  '#334155',

  // Erreur
  red:        '#EF4444',
  redDim:     '#FEF2F2',
  redText:    '#DC2626',

  // Primaire / information
  blue:       '#2563EB',
  blueDim:    '#EFF6FF',
  blueText:   '#1D4ED8',
} as const;

// Rayons — mêmes crans fonctionnels que le Web.
export const radius = {
  xs: 6,
  sm: 6,
  md: 10,
  lg: 14,
  xl: 18,
} as const;

export default colors;
