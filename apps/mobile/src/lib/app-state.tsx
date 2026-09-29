/**
 * App-wide preferences: language (and RTL), appearance, trip stage, interests
 * and the anonymous id. Persisted locally so guests keep them without an
 * account (Master Plan §18, §37, §48).
 */
import {
  isRTL as localeIsRTL,
  type Locale,
  type MessageKey,
  resolveLocale,
  translate,
} from '@comemorocco/i18n';
import type { TripStage } from '@comemorocco/shared';
import { type ColorScheme, colors, type ColorTokens } from '@comemorocco/ui';
import { getLocales } from 'expo-localization';
import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { I18nManager, Platform, useColorScheme } from 'react-native';

import { randomId } from './ids';
import { readJson, writeJson } from './storage';

export type ThemePreference = 'system' | 'light' | 'dark';

export interface Preferences {
  locale: Locale | null; // null = follow the device
  theme: ThemePreference;
  tripStage: TripStage | null;
  interests: string[];
  onboarded: boolean;
  anonymousId: string;
}

const DEFAULTS: Preferences = {
  locale: null,
  theme: 'system',
  tripStage: null,
  interests: [],
  onboarded: false,
  anonymousId: '',
};

interface AppState {
  ready: boolean;
  prefs: Preferences;
  locale: Locale;
  rtl: boolean;
  /** Native layout direction lags a language switch until the app restarts. */
  rtlRestartNeeded: boolean;
  scheme: ColorScheme;
  colors: ColorTokens;
  t: (key: MessageKey, vars?: Record<string, string | number>) => string;
  update: (patch: Partial<Preferences>) => void;
}

const AppContext = createContext<AppState | null>(null);

function applyDirection(rtl: boolean): void {
  if (Platform.OS === 'web') {
    if (typeof document !== 'undefined') {
      document.documentElement.dir = rtl ? 'rtl' : 'ltr';
      document.documentElement.lang = rtl ? 'ar' : document.documentElement.lang;
    }
    return;
  }
  I18nManager.allowRTL(true);
  // Native layout direction switches on the next launch.
  if (I18nManager.isRTL !== rtl) I18nManager.forceRTL(rtl);
}

export function AppStateProvider({ children }: { children: ReactNode }) {
  const [prefs, setPrefs] = useState<Preferences>(DEFAULTS);
  const [ready, setReady] = useState(false);
  const systemScheme = useColorScheme();

  useEffect(() => {
    let alive = true;
    readJson<Partial<Preferences>>('prefs', {}).then((stored) => {
      if (!alive) return;
      const merged = { ...DEFAULTS, ...stored };
      if (!merged.anonymousId) merged.anonymousId = randomId();
      setPrefs(merged);
      setReady(true);
      writeJson('prefs', merged);
    });
    return () => {
      alive = false;
    };
  }, []);

  const locale: Locale = prefs.locale ?? resolveLocale(getLocales().map((l) => l.languageTag));
  const rtl = localeIsRTL(locale);

  useEffect(() => {
    if (ready) applyDirection(rtl);
  }, [ready, rtl]);
  // I18nManager.isRTL keeps the direction the app launched with.
  const rtlRestartNeeded = ready && Platform.OS !== 'web' && I18nManager.isRTL !== rtl;

  const scheme: ColorScheme =
    prefs.theme === 'system' ? (systemScheme === 'dark' ? 'dark' : 'light') : prefs.theme;

  const update = useCallback((patch: Partial<Preferences>) => {
    setPrefs((current) => {
      const next = { ...current, ...patch };
      writeJson('prefs', next);
      return next;
    });
  }, []);

  const t = useCallback(
    (key: MessageKey, vars?: Record<string, string | number>) => translate(locale, key, vars),
    [locale],
  );

  const value = useMemo<AppState>(
    () => ({ ready, prefs, locale, rtl, rtlRestartNeeded, scheme, colors: colors[scheme], t, update }),
    [ready, prefs, locale, rtl, rtlRestartNeeded, scheme, t, update],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): AppState {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be used inside AppStateProvider');
  return ctx;
}
