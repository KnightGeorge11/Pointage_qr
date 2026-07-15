// theme/colors.ts
//
// Palette partagée par toute l'app mobile — reprend exactement les
// variables CSS de l'app web (pointage/templates/pointage/base.html)
// pour que web / mobile / desktop se ressemblent visuellement.
//
// Toujours importer les couleurs depuis ce fichier plutôt que d'écrire
// des couleurs en dur dans un écran : ça garantit que l'app reste
// cohérente si la palette évolue un jour.

export const colors = {
  // Neutres (texte / fonds sombres)
  ink:        '#0b0e17',
  inkSoft:    '#1c2235',
  inkMuted:   '#374163',

  // Fonds clairs
  surface:    '#f2f4f8',
  surfaceAlt: '#e8eaf0',
  white:      '#ffffff',

  // Bordures
  line:       '#dde1ec',
  lineSoft:   '#eceef5',

  // Sémantique — succès
  green:      '#00c27a',
  greenDim:   '#e4f9f1',
  greenText:  '#007a4d',

  // Sémantique — avertissement / garde de nuit
  amber:      '#f5a623',
  amberDim:   '#fef4e3',
  amberText:  '#a86f00',

  // Sémantique — erreur
  red:        '#e8344a',
  redDim:     '#fdeaed',
  redText:    '#b01f32',

  // Accent — liens, info, actions secondaires
  blue:       '#2962ff',
  blueDim:    '#e6ecff',
  blueText:   '#1940cc',
} as const;

// Rayons de bordure — mêmes crans que le web (--r-xs à --r-xl)
export const radius = {
  xs: 4,
  sm: 6,
  md: 10,
  lg: 14,
  xl: 18,
} as const;

export default colors;
