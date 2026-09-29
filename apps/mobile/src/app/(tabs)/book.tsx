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
import { catalog, destinationName, type ListingCategory, listingsFor } from '@/data/catalog';
import { useApp } from '@/lib/app-state';
import { openPartner } from '@/lib/links';

const CATEGORIES: { id: ListingCategory; label: MessageKey; icon: IconName }[] = [
  { id: 'stay', label: 'book.stays', icon: 'bed-outline' },
  { id: 'experience', label: 'book.experiences', icon: 'compass-outline' },
  { id: 'car', label: 'book.cars', icon: 'car-outline' },
  { id: 'transfer', label: 'book.transfers', icon: 'airplane-outline' },
  { id: 'driver', label: 'book.drivers', icon: 'person-outline' },
];

export default function Book() {
  const { t, colors, locale, prefs } = useApp();
  const params = useLocalSearchParams<{ category?: ListingCategory; destination?: string }>();
  const [category, setCategory] = useState<ListingCategory>(params.category ?? 'experience');
  const [destination, setDestination] = useState<string | null>(params.destination ?? null);

  const items = useMemo(() => listingsFor({ category, destination }), [category, destination]);
  // Programs (Booking.com, car rental…) cover all of Morocco, so they stay
  // visible whatever city is selected.
  const shown = useMemo(
    () => (destination ? [...items, ...listingsFor({ category }).filter((l) => l.destination === null)] : items),
    [items, destination, category],
  );

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
                <Chip key={c.id} label={t(c.label)} icon={c.icon} selected={category === c.id} onPress={() => setCategory(c.id)} />
              ))}
            </ScrollView>
            {category === 'experience' || category === 'transfer' ? (
              <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: spacing.sm }}>
                <Chip label={t('common.seeAll')} selected={!destination} onPress={() => setDestination(null)} />
                {catalog.destinations
                  .filter((d) => d.listing_count > 0)
                  .map((d) => (
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
        renderItem={({ item }) => <ListingRow listing={item} onPress={() => openPartner(item.id, 'book', prefs.anonymousId)} />}
        ListFooterComponent={<Row style={{ height: spacing.xl }} />}
      />
    </View>
  );
}
