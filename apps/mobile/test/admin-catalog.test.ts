import { describe, expect, it } from 'vitest';

import { checkDraft, EMPTY_DRAFT, toDraft, toPayload } from '../src/lib/admin-catalog-model';

describe('admin catalogue drafts', () => {
  const draft = { ...EMPTY_DRAFT, title: 'Riad Dar Anika', destination_id: 'fes', price: '900', link_url: 'https://riad.example/book' };

  it('checks the same rules as the database', () => {
    expect(checkDraft(draft)).toBeNull();
    expect(checkDraft({ ...draft, title: 'Ri' })).toBe('title');
    expect(checkDraft({ ...draft, price: '9,50' })).toBe('price');
    expect(checkDraft({ ...draft, image_url: 'http://x.example/a.jpg' })).toBe('image');
    expect(checkDraft({ ...draft, link_url: 'javascript:alert(1)' })).toBe('link');
  });

  it('stores prices in centimes and round-trips through the admin row', () => {
    const payload = toPayload(draft);
    expect(payload).toMatchObject({ price_from_minor: 90000, currency: 'MAD', link_is_partner: false });
    expect(payload).not.toHaveProperty('id');
    const back = toDraft({
      id: 'ADM-1', kind: 'direct', category: 'stay', subtype: 'riad', title: 'Riad Dar Anika', subtitle: null, description: null,
      destination_id: 'fes', partner_name: 'Booking.com', status: 'published', price_from_minor: 90000, currency: 'MAD',
      image_url: null, website_url: null, partner_url: 'https://www.booking.com/x', updated_at: '2026-10-02T00:00:00Z',
    });
    expect(back).toMatchObject({ id: 'ADM-1', price: '900', link_url: 'https://www.booking.com/x', link_is_partner: true });
  });
});
