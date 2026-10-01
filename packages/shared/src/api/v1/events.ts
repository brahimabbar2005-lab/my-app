/**
 * Analytics event taxonomy and attribution (Master Plan §26–27, §40).
 *
 * One list, used by the app to emit and by the database (analytics_events)
 * to store, so "does AI generate more bookings than Explore?" is answerable.
 */
import { z } from 'zod';

export const EventName = z.enum([
  'app_opened',
  'onboarding_completed',
  'search_started',
  'destination_viewed',
  'listing_viewed',
  'article_opened',
  'ai_started',
  'ai_message_sent',
  'ai_recommendation_clicked',
  'trip_created',
  'trip_item_added',
  'affiliate_clicked',
  'affiliate_conversion',
  'community_post_created',
  'community_post_viewed',
  'community_comment_created',
  'content_reported',
  'user_blocked',
  'provider_contacted',
  'booking_started',
  'booking_confirmed',
  'location_permission_requested',
  'location_permission_result',
  'account_deleted',
]);
export type EventName = z.infer<typeof EventName>;

/** Where the traveller came from / which surface produced the action. */
export const Source = z.enum([
  'explore',
  'book',
  'ai',
  'community',
  'my_trip',
  'search',
  'deeplink',
  'website',
  'push',
  'unknown',
]);
export type Source = z.infer<typeof Source>;

export const TripStage = z.enum(['dreaming', 'planning', 'in_morocco']);
export type TripStage = z.infer<typeof TripStage>;

export const Attribution = z.object({
  source: Source.default('unknown'),
  campaign: z.string().max(100).optional(),
  utm_source: z.string().max(100).optional(),
  utm_medium: z.string().max(100).optional(),
  utm_campaign: z.string().max(100).optional(),
  first_touch: z.string().max(200).optional(),
});
export type Attribution = z.infer<typeof Attribution>;

export const AnalyticsEvent = z.object({
  name: EventName,
  anonymous_id: z.string().min(8).max(64),
  user_id: z.uuid().optional(),
  occurred_at: z.iso.datetime(),
  platform: z.enum(['ios', 'android', 'web']),
  app_version: z.string().max(32).optional(),
  language: z.string().max(8).optional(),
  trip_stage: TripStage.optional(),
  destination: z.string().max(80).optional(),
  listing_id: z.string().max(128).optional(),
  affiliate_partner: z.string().max(80).optional(),
  attribution: Attribution.optional(),
  properties: z.record(z.string(), z.union([z.string(), z.number(), z.boolean(), z.null()])).default({}),
});
export type AnalyticsEvent = z.infer<typeof AnalyticsEvent>;
