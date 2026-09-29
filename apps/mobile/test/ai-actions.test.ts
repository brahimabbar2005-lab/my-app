import type { AIAction } from '@comemorocco/shared';
import { describe, expect, it, vi } from 'vitest';

import { isActionDone, runAction } from '../src/lib/ai-actions';

function target() {
  const items: { type: string; refId: string | null }[] = [];
  const saved: { refType: string; refId: string }[] = [];
  return {
    items,
    saved,
    addItem: vi.fn((i) => items.push({ type: i.type, refId: i.refId ?? null })),
    toggleSaved: vi.fn((p) => saved.push({ refType: p.refType, refId: p.refId })),
    isSaved: (t: string, id: string) => saved.some((s) => s.refType === t && s.refId === id),
    hasItem: (t: string, id: string) => items.some((i) => i.type === t && i.refId === id),
  };
}

const add: AIAction = {
  id: 'add_to_trip:listing:GYG-008',
  tool: 'add_to_trip',
  args: { item_type: 'listing', ref_id: 'GYG-008', title: 'Desert safari' },
  access: 'write',
  label: 'Desert safari',
  requires_confirmation: false,
};
const save: AIAction = {
  id: 'save_place:fes',
  tool: 'save_place',
  args: { place_id: 'fes', ref_type: 'destination' },
  access: 'write',
  label: 'Fes',
  requires_confirmation: false,
};

describe('AI actions', () => {
  it('adds to the trip for a guest on tap, once', () => {
    const t = target();
    expect(isActionDone(add, t)).toBe(false);
    expect(runAction(add, t, { signedIn: false })).toBe('done');
    expect(t.items).toEqual([{ type: 'listing', refId: 'GYG-008' }]);
    expect(isActionDone(add, t)).toBe(true);
  });

  it('saves a place without toggling it off when tapped twice', () => {
    const t = target();
    runAction(save, t, { signedIn: false });
    runAction(save, t, { signedIn: false });
    expect(t.saved).toEqual([{ refType: 'destination', refId: 'fes' }]);
  });

  it('rejects tampered or unknown actions', () => {
    const t = target();
    expect(runAction({ ...add, args: { ...add.args, sneaky: 1 } }, t, { signedIn: true })).toBe('rejected');
    expect(runAction({ ...add, args: { item_type: 'booking', ref_id: 'x' } }, t, { signedIn: true })).toBe('rejected');
    expect(runAction({ ...add, tool: 'make_payment', args: { booking_id: 'b', amount_minor: 1, currency: 'MAD' } } as AIAction, t, { signedIn: false })).toBe('rejected');
    expect(t.addItem).not.toHaveBeenCalled();
  });
});
