import { describe, expect, it } from 'vitest';

import { colors, contrastRatio } from '../src';

const AA_TEXT = 4.5;
const AA_UI = 3;

describe.each(['light', 'dark'] as const)('%s palette', (scheme) => {
  const c = colors[scheme];

  it.each([
    ['text', 'background'],
    ['text', 'surface'],
    ['text', 'surfaceAlt'],
    ['textMuted', 'background'],
    ['textMuted', 'surface'],
    ['onPrimary', 'primary'],
    ['onSecondary', 'secondary'],
    ['onAccent', 'accent'],
    ['primary', 'surface'],
    ['secondary', 'surface'],
    ['error', 'surface'],
    ['warning', 'surface'],
    ['success', 'surface'],
  ] as const)('%s on %s meets AA for text', (fg, bg) => {
    expect(contrastRatio(c[fg], c[bg])).toBeGreaterThanOrEqual(AA_TEXT);
  });

  it('inactive tab icons meet AA for UI components', () => {
    expect(contrastRatio(c.tabInactive, c.surface)).toBeGreaterThanOrEqual(AA_UI);
  });
});
