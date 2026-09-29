import { describe, expect, it } from 'vitest';

import { authorizeToolCall, TOOL_ACCESS, ToolArgs } from '../src/api/v1/actions';
import { goUrl } from '../src/api/v1/affiliate';
import { isSiteUrl, withAppUtm } from '../src/api/v1/content';

describe('action authorization', () => {
  const guest = { signedIn: false, userRequested: false };
  const user = { signedIn: true, userRequested: true };

  it('every tool has an access level', () => {
    expect(Object.keys(TOOL_ACCESS).sort()).toEqual(Object.keys(ToolArgs).sort());
  });

  it('read tools execute automatically, even for guests', () => {
    expect(authorizeToolCall('search_activities', { destination: 'Fes' }, guest)).toEqual({
      outcome: 'execute',
      args: { destination: 'Fes', limit: 6 },
    });
  });

  it('write tools need a signed-in user who asked for it', () => {
    expect(authorizeToolCall('add_to_trip', { item_type: 'place', ref_id: 'p1' }, guest)).toMatchObject({
      outcome: 'rejected',
      reason: 'not_signed_in',
    });
    expect(
      authorizeToolCall('add_to_trip', { item_type: 'place', ref_id: 'p1' }, { signedIn: true, userRequested: false }),
    ).toMatchObject({ outcome: 'rejected', reason: 'not_requested' });
    expect(authorizeToolCall('add_to_trip', { item_type: 'place', ref_id: 'p1' }, user).outcome).toBe('execute');
  });

  it('guests may write their own device-local trip, but never pay', () => {
    const guestTap = { signedIn: false, userRequested: true, deviceLocal: true };
    expect(authorizeToolCall('add_to_trip', { item_type: 'listing', ref_id: 'GYG-008' }, guestTap).outcome).toBe('execute');
    expect(
      authorizeToolCall('add_to_trip', { item_type: 'listing', ref_id: 'GYG-008' }, { ...guestTap, userRequested: false }),
    ).toMatchObject({ outcome: 'rejected', reason: 'not_requested' });
    const pay = { booking_id: 'b1', amount_minor: 100, currency: 'MAD' };
    expect(authorizeToolCall('make_payment', pay, { ...guestTap, confirmed: true })).toMatchObject({
      outcome: 'rejected',
      reason: 'not_signed_in',
    });
  });

  it('payments always require confirmation', () => {
    const args = { booking_id: 'b1', amount_minor: 240000, currency: 'MAD' };
    expect(authorizeToolCall('make_payment', args, user).outcome).toBe('needs_confirmation');
    expect(authorizeToolCall('make_payment', args, { ...user, confirmed: true }).outcome).toBe('execute');
  });

  it('unknown tools and invalid or extra arguments are rejected', () => {
    expect(authorizeToolCall('delete_everything', {}, user)).toMatchObject({ reason: 'unknown_tool' });
    expect(authorizeToolCall('get_nearby_places', { lat: 200, lng: 0 }, user)).toMatchObject({ reason: 'invalid_args' });
    expect(authorizeToolCall('get_current_trip', { sneaky: true }, user)).toMatchObject({ reason: 'invalid_args' });
  });
});

describe('links', () => {
  it('adds app attribution to website links without overriding existing campaigns', () => {
    const url = new URL(withAppUtm('https://comemorocco.com/marrakech/?utm_campaign=summer'));
    expect(url.searchParams.get('utm_source')).toBe('app');
    expect(url.searchParams.get('utm_medium')).toBe('mobile');
    expect(url.searchParams.get('utm_campaign')).toBe('summer');
  });

  it('recognises only comemorocco.com as the site', () => {
    expect(isSiteUrl('https://comemorocco.com/x')).toBe(true);
    expect(isSiteUrl('https://www.comemorocco.com/x')).toBe(true);
    expect(isSiteUrl('https://gyg.me/abc')).toBe(false);
    expect(isSiteUrl('https://evilcomemorocco.com/')).toBe(false);
    expect(isSiteUrl('not a url')).toBe(false);
  });

  it('builds /go links and refuses unsafe listing ids', () => {
    expect(goUrl('https://go.test', 'GYG-008', { src: 'ai', platform: 'ios' })).toBe(
      'https://go.test/go/GYG-008?src=ai&platform=ios',
    );
    expect(() => goUrl('https://go.test', '../admin')).toThrow();
  });
});
