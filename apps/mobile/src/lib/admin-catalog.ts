/**
 * Admin catalogue: every offer (drafts included) and saving one. The
 * database refuses both for anyone not in admin_users (42501).
 */
import { type AdminListing, type ListingDraft, toPayload } from './admin-catalog-model';
import { supabase } from './supabase';

export * from './admin-catalog-model';

export async function fetchAdminListings(): Promise<{ data?: AdminListing[]; error?: string }> {
  if (!supabase) return { error: 'not_configured' };
  const { data, error } = await supabase.rpc('admin_listings');
  return error ? { error: error.message } : { data: (data ?? []) as AdminListing[] };
}

export async function saveListing(d: ListingDraft): Promise<{ id?: string; error?: string }> {
  if (!supabase) return { error: 'not_configured' };
  const { data, error } = await supabase.rpc('admin_save_listing', { p: toPayload(d) });
  return error ? { error: error.message } : { id: data as string };
}
