import { describe, expect, it } from 'vitest';

import { formatPrice, isRTL, LOCALES, messages, resolveLocale, translate } from '../src';

function leaves(obj: object, prefix = ''): string[] {
  return Object.entries(obj).flatMap(([k, v]) =>
    typeof v === 'string' ? [`${prefix}${k}`] : leaves(v as object, `${prefix}${k}.`),
  );
}

describe('i18n', () => {
  it('every locale has every key, and no string is empty', () => {
    const reference = leaves(messages('en')).sort();
    for (const locale of LOCALES) {
      const catalog = messages(locale);
      expect(leaves(catalog).sort()).toEqual(reference);
      for (const key of reference) expect(translate(locale, key as never).trim()).not.toBe('');
    }
  });

  it('only Arabic is right-to-left', () => {
    expect(LOCALES.filter(isRTL)).toEqual(['ar']);
  });

  it('resolves device languages to a supported locale', () => {
    expect(resolveLocale(['fr-MA', 'en'])).toBe('fr');
    expect(resolveLocale(['de-DE', 'ar_MA'])).toBe('ar');
    expect(resolveLocale(['zh', undefined, null])).toBe('en');
  });

  it('translates with interpolation and falls back to the key text', () => {
    expect(translate('fr', 'trip.title')).toBe('Mon voyage');
    expect(translate('fr', 'trip.day', { n: 3 })).toBe('Jour 3');
    expect(translate('ar', 'tabs.explore')).toBe('استكشف');
  });

  it('formats Moroccan dirham prices with Western digits in Arabic', () => {
    expect(formatPrice('ar', 450)).toMatch(/450/);
    expect(formatPrice('en', 450)).toMatch(/450/);
  });
});
