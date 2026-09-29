/**
 * Analytics (Master Plan §26, §40). Events are validated against the shared
 * taxonomy and buffered; with Supabase configured they are written to
 * analytics_events in small batches. No personal data beyond the anonymous
 * id and, when signed in, the user id.
 */
import { AnalyticsEvent, type EventName } from '@comemorocco/shared';
import Constants from 'expo-constants';
import { Platform } from 'react-native';

import { supabase } from './supabase';

type Extra = Partial<Omit<AnalyticsEvent, 'name' | 'anonymous_id' | 'occurred_at' | 'platform'>>;

let anonymousId = '';
let context: Extra = {};
const queue: AnalyticsEvent[] = [];
let timer: ReturnType<typeof setTimeout> | null = null;

export function configureAnalytics(id: string, ctx: Extra) {
  anonymousId = id;
  context = ctx;
}

export function track(name: EventName, extra: Extra = {}) {
  if (!anonymousId) return;
  const parsed = AnalyticsEvent.safeParse({
    name,
    anonymous_id: anonymousId,
    occurred_at: new Date().toISOString(),
    platform: Platform.OS === 'ios' || Platform.OS === 'android' ? Platform.OS : 'web',
    app_version: Constants.expoConfig?.version,
    ...context,
    ...extra,
    properties: { ...(extra.properties ?? {}) },
  });
  if (!parsed.success) {
    if (__DEV__) console.warn('analytics: dropped invalid event', name, parsed.error.issues);
    return;
  }
  queue.push(parsed.data);
  if (!timer) timer = setTimeout(flush, 5000);
}

async function flush() {
  timer = null;
  const batch = queue.splice(0, 50);
  if (!batch.length) return;
  if (!supabase) {
    if (__DEV__) console.log('analytics', batch.map((e) => e.name).join(', '));
    return;
  }
  const { error } = await supabase.from('analytics_events').insert(
    batch.map((e) => ({
      name: e.name,
      anonymous_id: e.anonymous_id,
      occurred_at: e.occurred_at,
      platform: e.platform,
      app_version: e.app_version ?? null,
      language: e.language ?? null,
      trip_stage: e.trip_stage ?? null,
      destination: e.destination ?? null,
      listing_id: e.listing_id ?? null,
      affiliate_partner: e.affiliate_partner ?? null,
      attribution: e.attribution ?? null,
      properties: e.properties,
    })),
  );
  if (error && __DEV__) console.warn('analytics flush failed', error.message);
}
