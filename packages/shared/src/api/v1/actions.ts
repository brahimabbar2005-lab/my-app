/**
 * AI tools and actions, v1 (Master Plan §13–14, §18–19).
 *
 * The AI proposes; the platform decides. Every tool the AI can call is listed
 * here with its access level, and every call is validated against its
 * argument schema before execution and logged (ai_tool_calls).
 *
 *   read     executes automatically
 *   write    executes only when the user explicitly asked for it
 *   confirm  never executes without a confirmation step in the UI
 *
 * The Python service will mirror these with Pydantic when the tool layer is
 * built (Phase 4). Defining them now fixes the shape both sides build to.
 */
import { z } from 'zod';

export const AccessLevel = z.enum(['read', 'write', 'confirm']);
export type AccessLevel = z.infer<typeof AccessLevel>;

const id = z.string().min(1).max(128);
const destination = z.string().min(1).max(80);

/** Argument schemas, one per tool. Strict: unknown arguments are rejected. */
export const ToolArgs = {
  search_content: z.strictObject({ query: z.string().min(1).max(300), destination: destination.optional() }),
  search_destinations: z.strictObject({ query: z.string().min(1).max(200) }),
  search_activities: z.strictObject({
    destination: destination.optional(),
    query: z.string().max(200).optional(),
    limit: z.number().int().min(1).max(20).default(6),
  }),
  search_listings: z.strictObject({
    destination: destination.optional(),
    category: z.enum(['stay', 'experience', 'car', 'transfer', 'driver']).optional(),
    query: z.string().max(200).optional(),
    limit: z.number().int().min(1).max(20).default(6),
  }),
  get_destination: z.strictObject({ destination_id: id }),
  get_user_profile: z.strictObject({}),
  get_current_trip: z.strictObject({}),
  get_weather: z.strictObject({ destination, date: z.iso.date().optional() }),
  get_nearby_places: z.strictObject({
    lat: z.number().min(-90).max(90),
    lng: z.number().min(-180).max(180),
    radius_m: z.number().int().min(100).max(20000).default(1500),
    category: z.string().max(40).optional(),
  }),
  get_route: z.strictObject({ from: z.string().max(120), to: z.string().max(120), mode: z.string().max(20).optional() }),
  get_transport_options: z.strictObject({ from: destination, to: destination }),
  get_affiliate_options: z.strictObject({ category: z.string().max(40), destination: destination.optional() }),
  search_community: z.strictObject({ query: z.string().min(1).max(300), destination: destination.optional() }),
  open_article: z.strictObject({ content_id: id }),
  generate_booking_link: z.strictObject({ listing_id: id }),
  save_place: z.strictObject({ place_id: id }),
  add_to_trip: z.strictObject({ trip_id: id.optional(), item_type: z.enum(['place', 'listing', 'activity', 'note']), ref_id: id.optional(), day: z.number().int().min(1).max(60).optional(), title: z.string().max(200).optional() }),
  remove_from_trip: z.strictObject({ trip_item_id: id }),
  update_itinerary: z.strictObject({
    trip_id: id,
    changes: z.array(z.strictObject({ trip_item_id: id, day: z.number().int().min(1).max(60).optional(), position: z.number().int().min(0).optional() })).min(1).max(50),
  }),
  make_payment: z.strictObject({ booking_id: id, amount_minor: z.number().int().positive(), currency: z.string().length(3) }),
} as const;

export type ToolName = keyof typeof ToolArgs;

export const TOOL_ACCESS: Record<ToolName, AccessLevel> = {
  search_content: 'read',
  search_destinations: 'read',
  search_activities: 'read',
  search_listings: 'read',
  get_destination: 'read',
  get_user_profile: 'read',
  get_current_trip: 'read',
  get_weather: 'read',
  get_nearby_places: 'read',
  get_route: 'read',
  get_transport_options: 'read',
  get_affiliate_options: 'read',
  search_community: 'read',
  open_article: 'read',
  generate_booking_link: 'read',
  save_place: 'write',
  add_to_trip: 'write',
  remove_from_trip: 'write',
  update_itinerary: 'write',
  make_payment: 'confirm',
};

export const ToolName = z.enum(Object.keys(ToolArgs) as [ToolName, ...ToolName[]]);

/** One tool call the AI proposed, as stored in ai_tool_calls. */
export const ToolCall = z.object({
  id: z.string(),
  tool: ToolName,
  args: z.record(z.string(), z.unknown()),
  requested_at: z.iso.datetime(),
});
export type ToolCall = z.infer<typeof ToolCall>;

/** A write/confirm action surfaced to the UI (e.g. an "Add to My Trip" button). */
export const AIAction = z.object({
  id: z.string(),
  tool: ToolName,
  args: z.record(z.string(), z.unknown()),
  access: AccessLevel,
  label: z.string(),
  requires_confirmation: z.boolean(),
});
export type AIAction = z.infer<typeof AIAction>;

export type ActionDecision =
  | { outcome: 'execute'; args: Record<string, unknown> }
  | { outcome: 'needs_confirmation'; args: Record<string, unknown> }
  | { outcome: 'rejected'; reason: 'unknown_tool' | 'invalid_args' | 'not_signed_in' | 'not_requested'; detail?: string };

/**
 * The action validator (Master Plan §19):
 *   proposed action → validate args → permission check → confirmation → execute.
 *
 * `userRequested` is whether the user explicitly asked for this action in
 * their message (decided by the orchestrator, never by the model alone).
 */
export function authorizeToolCall(
  tool: string,
  args: unknown,
  ctx: { signedIn: boolean; userRequested: boolean; confirmed?: boolean },
): ActionDecision {
  if (!(tool in ToolArgs)) return { outcome: 'rejected', reason: 'unknown_tool', detail: tool };
  const name = tool as ToolName;
  const parsed = ToolArgs[name].safeParse(args ?? {});
  if (!parsed.success) {
    return { outcome: 'rejected', reason: 'invalid_args', detail: parsed.error.issues.map((i) => i.message).join('; ') };
  }
  const access = TOOL_ACCESS[name];
  const data = parsed.data as Record<string, unknown>;
  if (access === 'read') return { outcome: 'execute', args: data };
  if (!ctx.signedIn) return { outcome: 'rejected', reason: 'not_signed_in' };
  if (access === 'write') {
    return ctx.userRequested ? { outcome: 'execute', args: data } : { outcome: 'rejected', reason: 'not_requested' };
  }
  // confirm: explicit request AND a UI confirmation, every time.
  if (!ctx.userRequested) return { outcome: 'rejected', reason: 'not_requested' };
  return ctx.confirmed ? { outcome: 'execute', args: data } : { outcome: 'needs_confirmation', args: data };
}
