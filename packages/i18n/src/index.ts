/**
 * UI strings and locale helpers.
 *
 * UI languages: English, French, Arabic (RTL), Spanish. AI answer languages
 * are decided and evaluated separately by the AI service (Master Plan §47);
 * Darija is conversational only and not a UI language.
 */
import { ar } from './locales/ar';
import { en, type Messages } from './locales/en';
import { es } from './locales/es';
import { fr } from './locales/fr';

export type { Messages };

export const LOCALES = ['en', 'fr', 'ar', 'es'] as const;
export type Locale = (typeof LOCALES)[number];
export const DEFAULT_LOCALE: Locale = 'en';

export const LOCALE_NAMES: Record<Locale, string> = {
  en: 'English',
  fr: 'Français',
  ar: 'العربية',
  es: 'Español',
};

const catalogs: Record<Locale, Messages> = { en, fr, ar, es };

const RTL_LOCALES: ReadonlySet<Locale> = new Set(['ar']);

export function isRTL(locale: Locale): boolean {
  return RTL_LOCALES.has(locale);
}

/** Best supported locale for a list of device language tags, e.g. ["fr-MA", "ar"]. */
export function resolveLocale(tags: readonly (string | null | undefined)[]): Locale {
  for (const tag of tags) {
    const base = tag?.toLowerCase().split(/[-_]/)[0];
    if (base && (LOCALES as readonly string[]).includes(base)) return base as Locale;
  }
  return DEFAULT_LOCALE;
}

export function messages(locale: Locale): Messages {
  return catalogs[locale] ?? catalogs[DEFAULT_LOCALE];
}

type Leaves<T, P extends string = ''> = {
  [K in keyof T & string]: T[K] extends string ? `${P}${K}` : Leaves<T[K], `${P}${K}.`>;
}[keyof T & string];
export type MessageKey = Leaves<Messages>;

/** Look up "section.key", with {name} interpolation. Falls back to English. */
export function translate(locale: Locale, key: MessageKey, vars?: Record<string, string | number>): string {
  const lookup = (catalog: Messages): string | undefined => {
    let node: unknown = catalog;
    for (const part of key.split('.')) node = (node as Record<string, unknown> | undefined)?.[part];
    return typeof node === 'string' ? node : undefined;
  };
  const text = lookup(messages(locale)) ?? lookup(en) ?? key;
  if (!vars) return text;
  return text.replace(/\{(\w+)\}/g, (match, name: string) => (name in vars ? String(vars[name]) : match));
}

/** Locale-aware number formatting (Arabic uses Western digits in Morocco). */
export function formatNumber(locale: Locale, value: number, options?: Intl.NumberFormatOptions): string {
  const tag = locale === 'ar' ? 'ar-MA-u-nu-latn' : locale;
  return new Intl.NumberFormat(tag, options).format(value);
}

export function formatPrice(locale: Locale, amount: number, currency = 'MAD'): string {
  return formatNumber(locale, amount, { style: 'currency', currency, maximumFractionDigits: 0 });
}
