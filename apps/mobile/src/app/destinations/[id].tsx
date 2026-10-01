/**
 * Destination page. Also the deep-link target for
 * https://comemorocco.com/destinations/<id> (Universal / App Links).
 */
import { radii, spacing } from '@comemorocco/ui';
import { router, Stack, useLocalSearchParams } from 'expo-router';
import { StyleSheet, View } from 'react-native';

import { ArticleCard, ListingRow, ZelligeStar } from '@/components/brand';
import { AddToTripButton, SaveButton } from '@/components/trip-buttons';
import { Button, EmptyState, Screen, SectionHeader, T } from '@/components/ui';
import { destinationName, destinationTagline, getDestination, listingsFor } from '@/data/catalog';
import { useArticles } from '@/data/content';
import { useApp } from '@/lib/app-state';
import { openArticle, openPartner } from '@/lib/links';

export default function DestinationScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { t, locale, prefs } = useApp();
  const destination = id ? getDestination(id) : undefined;
  const articles = useArticles(destination?.id ?? null, 6);

  if (!destination) {
    return (
      <Screen edges={[]}>
        <Stack.Screen options={{ title: t('explore.destinations') }} />
        <EmptyState icon="map-outline" title={t('explore.chooseCity')}>
          <Button label={t('tabs.explore')} onPress={() => router.replace('/')} />
        </EmptyState>
      </Screen>
    );
  }

  const name = destinationName(destination, locale);
  const experiences = listingsFor({ destination: destination.id });

  return (
    <Screen edges={[]}>
      <Stack.Screen options={{ title: name }} />
      <View style={[styles.hero, { backgroundColor: destination.hue }]}>
        <ZelligeStar size={260} color="#FFFFFF" opacity={0.12} style={{ position: 'absolute', top: -70, end: -60 }} />
        <View style={{ position: 'absolute', top: spacing.lg, end: spacing.lg }}>
          <SaveButton refType="destination" refId={destination.id} title={name} size={28} onDark />
        </View>
        <T variant="display" style={{ color: '#FFFFFF' }}>
          {name}
        </T>
        <T style={{ color: 'rgba(255,255,255,0.92)' }}>{destinationTagline(destination, locale)}</T>
        <T variant="caption" style={{ color: 'rgba(255,255,255,0.85)' }}>
          {destination.region}
        </T>
      </View>

      <View style={{ gap: spacing.sm }}>
        <AddToTripButton item={{ type: 'destination', refId: destination.id, title: name }} />
        {destination.guide_url ? (
          <Button label={t('common.readFullGuide')} icon="book-outline" onPress={() => openArticle(destination.guide_url!, 'destination')} />
        ) : null}
        <Button
          label={t('trip.askAiToPlan')}
          kind="secondary"
          icon="sparkles-outline"
          onPress={() => router.push({ pathname: '/ai', params: { q: `What should I know before visiting ${destination.name.en}?` } })}
        />
      </View>

      {experiences.length ? (
        <View style={{ gap: spacing.md }}>
          <SectionHeader title={t('book.experiences')} />
          {experiences.map((l) => (
            <ListingRow key={l.id} listing={l} onPress={() => openPartner(l.id, 'explore', prefs.anonymousId)} />
          ))}
        </View>
      ) : null}

      {articles.items.length ? (
        <View style={{ gap: spacing.md }}>
          <SectionHeader title={t('explore.guides')} />
          {articles.items.map((a) => (
            <ArticleCard key={a.id} title={a.title} excerpt={a.excerpt} url={a.canonical_url} onPress={() => openArticle(a.canonical_url)} />
          ))}
        </View>
      ) : null}
    </Screen>
  );
}

const styles = StyleSheet.create({
  hero: { borderRadius: radii.xl, padding: spacing.xl, paddingTop: spacing.xxxl * 2, gap: spacing.xs, overflow: 'hidden' },
});
