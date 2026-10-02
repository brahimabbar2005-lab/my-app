/** Admin catalogue model: drafts, checks and the save payload (pure). */
import type { ListingCategory, ListingSubtype } from '../data/catalog';

export type ListingStatus = 'draft' | 'published' | 'archived';

export interface AdminListing {
  id: string;
  kind: 'program' | 'activity' | 'direct';
  category: ListingCategory;
  subtype: ListingSubtype | null;
  title: string;
  subtitle: string | null;
  description: string | null;
  destination_id: string | null;
  partner_name: string | null;
  status: ListingStatus;
  price_from_minor: number | null;
  currency: string | null;
  image_url: string | null;
  website_url: string | null;
  partner_url: string | null;
  updated_at: string;
}

export interface ListingDraft {
  id?: string;
  category: ListingCategory;
  subtype: ListingSubtype | null;
  title: string;
  subtitle: string;
  description: string;
  destination_id: string | null;
  partner_name: string;
  status: ListingStatus;
  /** Whole MAD, as typed; stored in centimes. */
  price: string;
  image_url: string;
  link_url: string;
  link_is_partner: boolean;
}

export const EMPTY_DRAFT: ListingDraft = {
  category: 'stay',
  subtype: 'riad',
  title: '',
  subtitle: '',
  description: '',
  destination_id: null,
  partner_name: '',
  status: 'draft',
  price: '',
  image_url: '',
  link_url: '',
  link_is_partner: false,
};

export function toDraft(l: AdminListing): ListingDraft {
  return {
    id: l.id,
    category: l.category,
    subtype: l.subtype,
    title: l.title,
    subtitle: l.subtitle ?? '',
    description: l.description ?? '',
    destination_id: l.destination_id,
    partner_name: l.partner_name ?? '',
    status: l.status,
    price: l.price_from_minor == null ? '' : String(Math.round(l.price_from_minor / 100)),
    image_url: l.image_url ?? '',
    link_url: l.partner_url ?? l.website_url ?? '',
    link_is_partner: Boolean(l.partner_url),
  };
}

export type DraftProblem = 'title' | 'price' | 'image' | 'link';

/** Same rules as the database, checked before sending. */
export function checkDraft(d: ListingDraft): DraftProblem | null {
  if (d.title.trim().length < 3) return 'title';
  if (d.price.trim() && !/^\d{1,7}$/.test(d.price.trim())) return 'price';
  if (d.image_url.trim() && !/^https:\/\/\S+$/.test(d.image_url.trim())) return 'image';
  if (d.link_url.trim() && !/^https:\/\/\S+$/.test(d.link_url.trim())) return 'link';
  return null;
}

/** The RPC payload. */
export function toPayload(d: ListingDraft): Record<string, unknown> {
  return {
    ...(d.id ? { id: d.id } : {}),
    category: d.category,
    subtype: d.subtype,
    title: d.title.trim(),
    subtitle: d.subtitle.trim(),
    description: d.description.trim(),
    destination_id: d.destination_id,
    partner_name: d.partner_name.trim(),
    status: d.status,
    price_from_minor: d.price.trim() ? Number(d.price.trim()) * 100 : null,
    currency: 'MAD',
    image_url: d.image_url.trim(),
    link_url: d.link_url.trim(),
    link_is_partner: d.link_is_partner,
  };
}
