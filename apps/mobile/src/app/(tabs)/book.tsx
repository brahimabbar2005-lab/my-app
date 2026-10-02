/**
 * Book (Master Plan §9). v0.1 is affiliate/external booking only: every
 * "View options" opens the partner through the worker's /go redirect, which
 * records the click. No prices are shown because none are known — the
 * partner site is the source of truth.
 */
import type { MessageKey } from '@comemorocco/i18n';
import { spacing } from '@comemorocco/ui';
import { useLocalSearchParams } from 'expo-router';
import { useMemo, useState } from 'react';
import { FlatList, ScrollView, View } from 'react-native';

import { ListingRow } from '@/components/brand';
import { Chip, EmptyState, type IconName, Row, T } from '@/components/ui';
import { catalog, destinationName, filterListings, type ListingCategory, type ListingSubtype } from '@/data/catalog';
import { useApp } from '@/lib/app-state';
import { openListing } from '@/lib/links';
import { useListings } from '@/lib/listings';

const CATEGORIES: { id: ListingCategory; label: MessageKey; icon: IconName }[] = [
  { id: 'stay', label: 'book.stays', icon: 'bed-outline' },
  { id: 'experience', label: 'book.experiences', icon: 'compass-outline' },
  { id: 'car', label: 'book.cars', icon: 'car-outline' },
  { id: 'transfer', label: 'book.transfers', icon: 'airplane-outline' },
  { id: 'driver', label: 'book.drivers', icon: 'person-outline' },
];

/** Type chips per category; only types that have offers are shown. */
const SUBTYPES: Partial<Record<ListingCategory, ListingSubtype[]>> = {
  stay: ['hotel', 'riad', 'hostel', 'guesthouse', 'camp', 'apartment', 'villa'],
  experience: ['tour', 'day_trip', 'activity', 'class'],
};

export default function Book() {
  const { t, colors, locale, prefs } = useApp();
  const params = useLocalSearchParams<{ category?: ListingCategory; destination?: string }>();
  const [category, setCategory] = useState<ListingCategory>(params.category ?? 'experience');
  const [destination, setDestination] = useState<string | null>(params.destination ?? null);
  const [subtype, setSubtype] = useState<ListingSubtype | null>(null);
  const all = useListings();

  const inCategory = useMemo(() => filterListings(all, { category }), [all, category]);
  const subtypes = useMemo(
    () => (SUBTYPES[category] ?? []).filter((st) => inCategory.some((l) => l.subtype === st)),
    [category, inCategory],
  );
  const cities = useMemo(
    () => catalog.destinations.filter((d) => inCategory.some((l) => l.destination === d.id)),
    [inCategory],
  );
  const shown = useMemo(() => {
    const items = filterListings(all, { category, destination, subtype });
    // Programs (Booking.com, car rental…) cover all of Morocco, so they stay
    // visible whatever city is selected (but not under a specific type).
    return destination && !subtype ? [...items, ...inCategory.filter((l) => l.destination === null)] : items;
  }, [all, category, destination, subtype, inCategory]);

  const chooseCategory = (c: ListingCategory) => {
    setCategory(c);
    setSubtype(null);
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.background }}>
      <FlatList
        data={category === 'driver' ? [] : shown}
        keyExtractor={(l) => l.id}
        contentContainerStyle={{ padding: spacing.lg, gap: spacing.md, maxWidth: 720, width: '100%', alignSelf: 'center' }}
        ListHeaderComponent={
          <View style={{ gap: spacing.md, marginBottom: spacing.sm }}>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: spacing.sm }}>
              {CATEGORIES.map((c) => (
                <Chip key={c.id} label={t(c.label)} icon={c.icon} selected={category === c.id} onPress={() => chooseCategory(c.id)} />
              ))}
            </ScrollView>
            {subtypes.length ? (
              <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: spacing.sm }}>
                <Chip label={t('book.allTypes')} selected={!subtype} onPress={() => setSubtype(null)} />
                {subtypes.map((st) => (
                  <Chip key={st} label={t(`book.subtype_${st}`)} selected={subtype === st} onPress={() => setSubtype(st)} />
                ))}
              </ScrollView>
            ) : null}
            {cities.length ? (
              <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: spacing.sm }}>
                <Chip label={t('common.seeAll')} selected={!destination} onPress={() => setDestination(null)} />
                {cities.map((d) => (
                    <Chip
                      key={d.id}
                      label={destinationName(d, locale)}
                      selected={destination === d.id}
                      onPress={() => setDestination(d.id)}
                    />
                  ))}
              </ScrollView>
            ) : null}
            <T variant="caption" tone="muted">
              {t('book.partnerDisclosure')}
            </T>
          </View>
        }
        ListEmptyComponent={
          category === 'driver' ? (
            <EmptyState icon="person-outline" title={`${t('book.drivers')} · ${t('common.comingSoon')}`} body={t('onboarding.inMoroccoHint')} />
          ) : (
            <EmptyState icon="compass-outline" title={t('common.comingSoon')} />
          )
        }
        renderItem={({ item }) => <ListingRow listing={item} onPress={() => openListing(item, 'book', prefs.anonymousId)} />}
        ListFooterComponent={<Row style={{ height: spacing.xl }} />}
      />
    </View>
  );
}
