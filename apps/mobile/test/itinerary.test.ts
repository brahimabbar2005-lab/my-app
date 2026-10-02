import { describe, expect, it } from 'vitest';

import { parseItinerary } from '../src/lib/itinerary';

const places = [
  { id: 'marrakech', names: ['Marrakech', 'Marrakesh', 'مراكش'] },
  { id: 'ouarzazate', names: ['Ouarzazate', 'ورزازات'] },
  { id: 'merzouga', names: ['Merzouga', 'Sahara', 'الصحراء'] },
  { id: 'fes', names: ['Fes', 'Fès', 'فاس'] },
];

describe('parseItinerary', () => {
  it('reads the plan from the answer in the screenshot', () => {
    const text = [
      '**7-Day Morocco Itinerary**',
      '• **Days 1–2:** Marrakech — explore the medina, Jemaa el-Fnaa.',
      '• **Days 3–4:** Atlas foothills — stay in Imlil or near Ait Benhaddou.',
      '• **Days 5–6:** Desert & Ouarzazate — drive through the Dades Valley, a night in the Sahara.',
      '• **Day 7:** Return to Marrakech or transfer to Casablanca/Fès.',
    ].join('\n');
    const plan = parseItinerary(text, places);
    expect(plan.map((d) => d.day)).toEqual([1, 2, 3, 4, 5, 6, 7]);
    expect(plan[0]).toMatchObject({ destinations: ['marrakech'], text: 'Marrakech — explore the medina, Jemaa el-Fnaa.' });
    expect(plan[2]!.destinations).toEqual([]);
    expect(plan[4]!.destinations).toEqual(['ouarzazate', 'merzouga']);
    expect(plan[6]!.destinations).toEqual(['marrakech', 'fes']);
  });

  it('reads French, Spanish and Arabic day labels', () => {
    expect(parseItinerary('Jour 1 : Fès, la médina\nJour 2 : Merzouga', places).map((d) => d.destinations)).toEqual([
      ['fes'],
      ['merzouga'],
    ]);
    expect(parseItinerary('Día 1: Marrakech\nDías 2-3: Sahara', places).map((d) => d.day)).toEqual([1, 2, 3]);
    expect(parseItinerary('اليوم ١: مراكش\nاليوم ٢: ورزازات', places).map((d) => d.destinations)).toEqual([
      ['marrakech'],
      ['ouarzazate'],
    ]);
  });

  it('is not fooled by prose', () => {
    expect(parseItinerary('Spend 2 days in Marrakech, then a day in the desert.', places)).toEqual([]);
    expect(parseItinerary('Day 1: Marrakech', places)).toEqual([]);
    expect(parseItinerary('Day 1: festivals and food\nDay 2: Marrakesh', places).map((d) => d.destinations)).toEqual([
      [],
      ['marrakech'],
    ]);
    expect(parseItinerary('Day 1: a\nDay 99: b\nDay 2: c', places).map((d) => d.day)).toEqual([1, 2]);
  });
});
