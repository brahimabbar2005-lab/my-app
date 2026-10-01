/**
 * AI chat contract, v1.
 *
 * Mirrors services/ai/app/schemas.py. Both sides are tested against the same
 * example payloads in contracts/v1/examples, so a change on one side that the
 * other does not accept fails CI (packages/shared/test/contract.test.ts and
 * services/ai/tests/test_contract.py).
 *
 * Unknown fields are allowed through (zod's default object behaviour strips
 * them) so the service can add fields without breaking older app builds.
 */
import { z } from 'zod';

import { AIAction } from './actions';

export const API_VERSION = 'v1' as const;

export const ChatMessage = z.object({
  role: z.enum(['user', 'assistant']),
  content: z.string(),
});
export type ChatMessage = z.infer<typeof ChatMessage>;

/** The app's My Trip as controlled context for the AI (Master Plan §20). */
export const TripContext = z.object({
  day_count: z.number().int().min(1).max(90).nullish(),
  destinations: z.array(z.string().max(80)).max(12).default([]),
  start_date: z
    .string()
    .regex(/^\d{4}-\d{2}-\d{2}$/)
    .nullish(),
});
export type TripContext = z.infer<typeof TripContext>;

export const ChatRequest = z.object({
  message: z.string().trim().min(1),
  session_id: z.string().nullish(),
  conversation_id: z.string().nullish(),
  page_url: z.string().nullish(),
  page_title: z.string().nullish(),
  locale: z.string().nullish(),
  trip_context: TripContext.nullish(),
});
export type ChatRequest = z.infer<typeof ChatRequest>;

/** A ComeMorocco page the answer points to. Opens the canonical website URL. */
export const ResourceCard = z.object({
  content_id: z.string(),
  title: z.string(),
  url: z.string(),
  anchor_text: z.string(),
  reason: z.string(),
  score: z.number(),
});
export type ResourceCard = z.infer<typeof ResourceCard>;

/** A commercial recommendation. Always rendered with its disclosure. */
export const AffiliateCard = z.object({
  affiliate_id: z.string(),
  name: z.string(),
  category: z.string(),
  url: z.string(),
  label: z.string(),
  reason: z.string(),
  disclosure: z
    .string()
    .default('Partner link — ComeMorocco may earn a commission if you book through it.'),
});
export type AffiliateCard = z.infer<typeof AffiliateCard>;

/** What the AI knows about the traveller's trip. Every field is optional. */
export const TripState = z.object({
  trip_duration_days: z.number().int().nullish(),
  travel_dates: z.string().nullish(),
  season: z.string().nullish(),
  party_adults: z.number().int().nullish(),
  party_children: z.number().int().nullish(),
  children_ages: z.array(z.string()).optional(),
  traveler_type: z.string().nullish(),
  destinations: z.array(z.string()).optional(),
  excluded_destinations: z.array(z.string()).optional(),
  origin: z.string().nullish(),
  arrival_city: z.string().nullish(),
  departure_city: z.string().nullish(),
  budget: z.string().nullish(),
  interests: z.array(z.string()).optional(),
  transport_preference: z.string().nullish(),
  travel_pace: z.string().nullish(),
  accommodation_preference: z.string().nullish(),
  constraints: z.array(z.string()).optional(),
  already_visited: z.array(z.string()).optional(),
});
export type TripState = z.infer<typeof TripState>;

/** A photo shown with an answer (Unsplash). Wherever it is shown, the
 * photographer and Unsplash must be credited, both linked. */
export const Photo = z.object({
  url: z.url(),
  thumb_url: z.url(),
  alt: z.string().default(''),
  photographer: z.string(),
  photographer_url: z.url(),
  source_url: z.url(),
});
export type Photo = z.infer<typeof Photo>;

export const ChatResponse = z.object({
  session_id: z.string(),
  conversation_id: z.string(),
  message_id: z.string(),
  answer: z.string(),
  resources: z.array(ResourceCard).default([]),
  affiliates: z.array(AffiliateCard).default([]),
  intents: z.array(z.string()).default([]),
  language: z.string().default('en'),
  trip_state: TripState.default({}),
  notices: z.array(z.string()).default([]),
  actions: z.array(AIAction).default([]),
  photos: z.array(Photo).default([]),
  latency_ms: z.number().default(0),
});
export type ChatResponse = z.infer<typeof ChatResponse>;

/** Error body returned with 400/429/500 — always carries a human answer. */
export const ChatError = z.object({
  error: z.string(),
  answer: z.string().optional(),
});
export type ChatError = z.infer<typeof ChatError>;

// ---------------------------------------------------------------- streaming
// POST /api/chat/stream emits server-sent events in this order:
//   meta → delta* → done       (or error at any point)

export const StreamMeta = z.object({
  session_id: z.string(),
  conversation_id: z.string(),
  actions: z.array(AIAction).default([]),
  photos: z.array(Photo).default([]),
  resources: z.array(ResourceCard).default([]),
  affiliates: z.array(AffiliateCard).default([]),
  notices: z.array(z.string()).default([]),
  intents: z.array(z.string()).default([]),
  language: z.string().default('en'),
  trip_state: TripState.optional(),
});
export const StreamDelta = z.object({ text: z.string() });
export const StreamDone = z.object({
  conversation_id: z.string(),
  message_id: z.string(),
  latency_ms: z.number(),
  trip_state: TripState.default({}),
});
export const StreamError = z.object({ answer: z.string() });

export type ChatStreamEvent =
  | { type: 'meta'; data: z.infer<typeof StreamMeta> }
  | { type: 'delta'; data: z.infer<typeof StreamDelta> }
  | { type: 'done'; data: z.infer<typeof StreamDone> }
  // `detail` is set by the client (not the service) when the request itself
  // failed: the address and reason, for development builds to display.
  | { type: 'error'; data: z.infer<typeof StreamError> & { detail?: string } };

export const FeedbackRequest = z.object({
  message_id: z.string(),
  helpful: z.boolean(),
  reason: z
    .enum([
      'incorrect',
      'outdated',
      'irrelevant',
      'too_long',
      'too_short',
      'did_not_answer',
      'bad_link',
      'other',
    ])
    .nullish(),
  comment: z.string().max(1000).nullish(),
});
export type FeedbackRequest = z.infer<typeof FeedbackRequest>;
