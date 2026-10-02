import { goUrl, isSiteUrl, type Source, withAppUtm } from '@comemorocco/shared';
import * as WebBrowser from 'expo-web-browser';
import { Platform } from 'react-native';

import type { Listing } from '@/data/catalog';

import { track } from './analytics';
import { config } from './config';

const platform = Platform.OS === 'ios' || Platform.OS === 'android' ? Platform.OS : 'web';

/** Open a comemorocco.com page (with app attribution) in the in-app browser. */
export async function openArticle(url: string, campaign = 'content') {
  const target = isSiteUrl(url) ? withAppUtm(url, campaign) : url;
  track('article_opened', { properties: { url } });
  await WebBrowser.openBrowserAsync(target);
}

/**
 * Open a partner offer. Always via the platform worker's /go redirect, which
 * records the click and resolves the affiliate URL server-side.
 */
export async function openPartner(listingId: string, source: Source, anonymousId?: string) {
  track('affiliate_clicked', { listing_id: listingId, properties: { source } });
  const url = goUrl(config.platformUrl, listingId, {
    src: source,
    platform,
    ...(anonymousId ? { aid: anonymousId } : {}),
  });
  await WebBrowser.openBrowserAsync(url);
}

/** Opens an offer: its direct booking page if it has one, else the partner redirect. */
export async function openListing(listing: Pick<Listing, 'id' | 'websiteUrl'>, source: Source, anonymousId?: string) {
  if (listing.websiteUrl) {
    track('affiliate_clicked', { listing_id: listing.id, properties: { source, direct: true } });
    await WebBrowser.openBrowserAsync(listing.websiteUrl);
    return;
  }
  await openPartner(listing.id, source, anonymousId);
}
