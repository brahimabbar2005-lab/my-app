/**
 * Runs an AI-proposed action after the traveller taps it (Master Plan §14, §19):
 *   proposal → authorizeToolCall (schema + permission) → execute → analytics.
 * Only trip actions exist in v0.2; anything else is rejected.
 */
import { type AIAction, authorizeToolCall } from '@comemorocco/shared';

import type { NewItem, SavedRefType, TripItemType } from './trip-model';

export interface ActionTarget {
  addItem: (item: NewItem) => void;
  toggleSaved: (place: { refType: SavedRefType; refId: string; title: string }) => void;
  isSaved: (refType: SavedRefType, refId: string) => boolean;
  hasItem: (type: TripItemType, refId: string) => boolean;
}

const ITEM_TYPES: Record<string, TripItemType> = {
  destination: 'destination',
  place: 'destination',
  listing: 'listing',
  activity: 'activity',
  article: 'article',
  note: 'note',
};

export type ActionResult = 'done' | 'rejected';

export function isActionDone(action: AIAction, target: ActionTarget): boolean {
  const args = action.args as Record<string, unknown>;
  if (action.tool === 'add_to_trip') {
    const type = ITEM_TYPES[String(args.item_type)];
    return !!type && typeof args.ref_id === 'string' && target.hasItem(type, args.ref_id);
  }
  if (action.tool === 'save_place') {
    return typeof args.place_id === 'string' && target.isSaved((args.ref_type as SavedRefType) ?? 'place', args.place_id);
  }
  return false;
}

export function runAction(action: AIAction, target: ActionTarget, ctx: { signedIn: boolean }): ActionResult {
  const decision = authorizeToolCall(action.tool, action.args, {
    signedIn: ctx.signedIn,
    userRequested: true, // only ever called from the traveller's tap
    deviceLocal: true, // My Trip lives on the device (and syncs when signed in)
  });
  if (decision.outcome !== 'execute') return 'rejected';
  const args = decision.args;
  if (action.tool === 'add_to_trip') {
    const type = ITEM_TYPES[String(args.item_type)];
    if (!type) return 'rejected';
    target.addItem({
      type,
      refId: typeof args.ref_id === 'string' ? args.ref_id : null,
      title: typeof args.title === 'string' ? args.title : action.label,
      day: typeof args.day === 'number' ? args.day : null,
    });
    return 'done';
  }
  if (action.tool === 'save_place') {
    const refType = (args.ref_type as SavedRefType) ?? 'place';
    const refId = String(args.place_id);
    if (!target.isSaved(refType, refId)) target.toggleSaved({ refType, refId, title: action.label });
    return 'done';
  }
  return 'rejected';
}
