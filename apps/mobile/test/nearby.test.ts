import { describe, expect, it } from 'vitest';

import { byDistance, distanceKm, OUTSIDE_KM } from '../src/lib/nearby';

const marrakech = { id: 'marrakech', lat: 31.6295, lng: -7.9811 };
const fes = { id: 'fes', lat: 34.0181, lng: -5.0078 };
const essaouira = { id: 'essaouira', lat: 31.5085, lng: -9.7595 };

describe('nearby', () => {
  it('measures great-circle distance', () => {
    expect(Math.round(distanceKm(marrakech, fes))).toBeGreaterThan(370);
    expect(Math.round(distanceKm(marrakech, fes))).toBeLessThan(400);
    expect(distanceKm(marrakech, marrakech)).toBe(0);
  });

  it('sorts destinations nearest first', () => {
    const jemaaElFna = { lat: 31.6258, lng: -7.9891 };
    const sorted = byDistance(jemaaElFna, [fes, essaouira, marrakech]);
    expect(sorted.map((d) => d.id)).toEqual(['marrakech', 'essaouira', 'fes']);
    expect(sorted[0]!.km).toBeLessThan(2);
  });

  it('a traveller in Paris is outside Morocco', () => {
    const paris = { lat: 48.8566, lng: 2.3522 };
    expect(byDistance(paris, [marrakech, fes, essaouira])[0]!.km).toBeGreaterThan(OUTSIDE_KM);
  });
});
