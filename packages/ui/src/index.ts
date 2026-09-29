/**
 * ComeMorocco design tokens (Master Plan §46).
 *
 * A small semantic palette: the Moroccan identity comes from photography,
 * type and a subtle zellige accent — not from using every colour everywhere.
 *   primary    terracotta   — main actions, active tab
 *   secondary  majorelle    — links, AI surface
 *   accent     saffron      — highlights, badges, ratings
 * Every text/background pair is checked for WCAG AA contrast in test/.
 */

export const palette = {
  terracotta700: '#9C3B26',
  terracotta600: '#B4462F',
  terracotta300: '#EE9B82',
  majorelle700: '#2A3F8F',
  majorelle600: '#3450A1',
  majorelle300: '#9DB1F2',
  saffron500: '#E0A526',
  saffron300: '#F3C969',
  sand50: '#FBF7F1',
  sand100: '#F4ECE0',
  sand200: '#E8DCCB',
  mint600: '#1F7A63',
  mint300: '#7FD1B9',
  ink900: '#1C1714',
  ink700: '#4A403A',
  ink500: '#6E625A',
  night900: '#12100E',
  night800: '#1C1916',
  night700: '#2A2521',
  night600: '#3A332D',
  cream100: '#F6EFE6',
  cream300: '#CBBFB2',
  red600: '#B3261E',
  red300: '#F2B8B5',
  amber700: '#8A5A00',
  amber300: '#F5C451',
} as const;

export interface ColorTokens {
  primary: string;
  onPrimary: string;
  secondary: string;
  onSecondary: string;
  accent: string;
  onAccent: string;
  background: string;
  surface: string;
  surfaceAlt: string;
  border: string;
  text: string;
  textMuted: string;
  success: string;
  warning: string;
  error: string;
  tabInactive: string;
}

export const colors: { light: ColorTokens; dark: ColorTokens } = {
  light: {
    primary: palette.terracotta600,
    onPrimary: '#FFFFFF',
    secondary: palette.majorelle600,
    onSecondary: '#FFFFFF',
    accent: palette.saffron500,
    onAccent: palette.ink900,
    background: palette.sand50,
    surface: '#FFFFFF',
    surfaceAlt: palette.sand100,
    border: palette.sand200,
    text: palette.ink900,
    textMuted: palette.ink500,
    success: palette.mint600,
    warning: palette.amber700,
    error: palette.red600,
    tabInactive: palette.ink500,
  },
  dark: {
    primary: palette.terracotta300,
    onPrimary: palette.night900,
    secondary: palette.majorelle300,
    onSecondary: palette.night900,
    accent: palette.saffron300,
    onAccent: palette.night900,
    background: palette.night900,
    surface: palette.night800,
    surfaceAlt: palette.night700,
    border: palette.night600,
    text: palette.cream100,
    textMuted: palette.cream300,
    success: palette.mint300,
    warning: palette.amber300,
    error: palette.red300,
    tabInactive: palette.cream300,
  },
};

export type ColorScheme = keyof typeof colors;

export const spacing = { xxs: 2, xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32, xxxl: 48 } as const;

export const radii = { sm: 8, md: 12, lg: 16, xl: 24, pill: 999 } as const;

export const typography = {
  display: { fontSize: 30, lineHeight: 36, fontWeight: '700' },
  title: { fontSize: 22, lineHeight: 28, fontWeight: '700' },
  heading: { fontSize: 18, lineHeight: 24, fontWeight: '600' },
  body: { fontSize: 16, lineHeight: 22, fontWeight: '400' },
  bodyStrong: { fontSize: 16, lineHeight: 22, fontWeight: '600' },
  caption: { fontSize: 13, lineHeight: 18, fontWeight: '400' },
  label: { fontSize: 12, lineHeight: 16, fontWeight: '600' },
} as const;

export const MAX_CONTENT_WIDTH = 720;

/** WCAG relative-luminance contrast ratio between two #RRGGBB colours. */
export function contrastRatio(a: string, b: string): number {
  const lum = (hex: string) => {
    const n = parseInt(hex.slice(1), 16);
    const channel = (c: number) => {
      const s = c / 255;
      return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
    };
    return 0.2126 * channel((n >> 16) & 255) + 0.7152 * channel((n >> 8) & 255) + 0.0722 * channel(n & 255);
  };
  const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x) as [number, number];
  return (hi + 0.05) / (lo + 0.05);
}
