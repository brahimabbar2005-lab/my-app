/**
 * Explore — the home screen (Master Plan §8). Adapts to the trip stage:
 * dreaming → inspiration first, planning → guides and experiences,
 * in Morocco → local help first. Location is never requested here; "Near me"
 * explains why before anything is asked (§15, §31).
 */
import { spacing } from '@comemorocco/ui';
import Ionicons from '@expo/vector-icons/Ionicons';
import * as Location from 'expo-location';
import { router } from 'expo-router';
import { useMemo, useState } from 'react';
import { FlatList, Modal, Pressable, ScrollView, StyleSheet, TextInput, View } from 'react-native';

import { ArticleCard, DestinationTile, ListingRow } from '@/components/brand';
import { Button, Card, Chip, Row, Screen, SectionHeader, T } from '@/components/ui';
import { articlesForInterests, catalog, destinationName, destinationTagline, listingsFor, searchCatalog } from '@/data/catalog';
import { useArticles } from '@/data/content';
import { track } from '@/lib/analytics';
import { useApp } from '@/lib/app-state';
import { byDistance, OUTSIDE_KM } from '@/lib/nearby';
import { openArticle, openPartner } from '@/lib/links';

export default function Explore() {
  const { t, colors, locale, prefs, update } = useApp();
  const [query, setQuery] = useState('');
  const [nearMeOpen, setNearMeOpen] = useState(false);
  const articles = useArticles(null, 8);
  const results = useMemo(() => searchCatalog(query, locale), [query, locale]);
  const popular = useMemo(() => listingsFor({ category: 'experience' }).filter((l) => l.destination).slice(0, 4), []);
  const openDestination = (id: string) => {
    track('destination_viewed', { destination: id, properties: { source: 'explore' } });
    router.push({ pathname: '/destinations/[id]', params: { id } });
  };

  const inMorocco = prefs.tripStage === 'in_morocco';

  return (
    <Screen edges={[]}>
      <View style={{ gap: spacing.md }}>
        <T variant="title">{t('explore.greeting')}</T>
        <View style={[styles.search, { backgroundColor: colors.surface, borderColor: colors.border }]}>
          <Ionicons name="search" size={18} color={colors.textMuted} />
          <TextInput
            value={query}
            onChangeText={setQuery}
            onSubmitEditing={() => track('search_started', { properties: { length: query.length } })}
            placeholder={t('explore.searchPlaceholder')}
            placeholderTextColor={colors.textMuted}
            style={[styles.searchInput, { color: colors.text }]}
            returnKeyType="search"
            accessibilityLabel={t('explore.searchPlaceholder')}
          />
          {query ? (
            <Pressable onPress={() => setQuery('')} hitSlop={8} accessibilityLabel={t('common.cancel')}>
              <Ionicons name="close-circle" size={18} color={colors.textMuted} />
            </Pressable>
          ) : null}
        </View>
        <Row style={{ flexWrap: 'wrap' }}>
          <Chip label={t('explore.nearMe')} icon="navigate-outline" onPress={() => setNearMeOpen(true)} />
          <Chip label={t('tabs.ai')} icon="sparkles-outline" onPress={() => router.push('/ai')} />
          <Chip label={t('trip.essentials')} icon="medkit-outline" onPress={() => router.push('/trip')} />
        </Row>
      </View>

      {query.trim().length >= 2 ? (
        <View style={{ gap: spacing.md }}>
          {results.destinations.map((d) => (
            <Pressable key={d.id} onPress={() => openDestination(d.id)}>
              <Card>
                <T variant="bodyStrong">{destinationName(d, locale)}</T>
                <T variant="caption" tone="muted">
                  {destinationTagline(d, locale)}
                </T>
              </Card>
            </Pressable>
          ))}
          {results.listings.map((l) => (
            <ListingRow key={l.id} listing={l} onPress={() => openPartner(l.id, 'search', prefs.anonymousId)} />
          ))}
          {results.articles.map((a) => (
            <ArticleCard key={a.id} title={a.title} excerpt={a.excerpt} url={a.canonical_url} onPress={() => openArticle(a.canonical_url)} />
          ))}
          {!results.destinations.length && !results.listings.length && !results.articles.length ? (
            <Card>
              <T tone="muted">{t('ai.subtitle')}</T>
              <Button label={t('tabs.ai')} icon="sparkles" onPress={() => router.push({ pathname: '/ai', params: { q: query } })} />
            </Card>
          ) : null}
        </View>
      ) : (
        <>
          {inMorocco ? (
            <Card style={{ backgroundColor: colors.surfaceAlt }}>
              <Row>
                <Ionicons name="compass" size={20} color={colors.primary} />
                <T variant="bodyStrong">{t('onboarding.inMorocco')}</T>
              </Row>
              <T tone="muted">{t('onboarding.inMoroccoHint')}</T>
              <Row style={{ flexWrap: 'wrap' }}>
                <Chip label={t('trip.emergency')} icon="call-outline" onPress={() => router.push('/trip')} />
                <Chip label={t('trip.phrasebook')} icon="chatbubbles-outline" onPress={() => router.push('/trip')} />
                <Chip label={t('explore.nearMe')} icon="navigate-outline" onPress={() => setNearMeOpen(true)} />
              </Row>
            </Card>
          ) : null}

          <View style={{ gap: spacing.md }}>
            <SectionHeader title={t('explore.destinations')} />
            <FlatList
              horizontal
              data={catalog.destinations}
              keyExtractor={(d) => d.id}
              showsHorizontalScrollIndicator={false}
              contentContainerStyle={{ gap: spacing.md }}
              renderItem={({ item }) => <DestinationTile destination={item} onPress={() => openDestination(item.id)} />}
            />
          </View>

          <View style={{ gap: spacing.md }}>
            <SectionHeader title={t('explore.guides')} />
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: spacing.md }}>
              {(articles.source === 'fallback' ? articlesForInterests(prefs.interests, 8) : articles.items).map((a) => (
                <ArticleCard
                  key={a.id}
                  width={260}
                  title={a.title}
                  excerpt={a.excerpt}
                  url={a.canonical_url}
                  onPress={() => openArticle(a.canonical_url)}
                />
              ))}
            </ScrollView>
          </View>

          <View style={{ gap: spacing.md }}>
            <SectionHeader title={t('explore.popularActivities')} action={t('common.seeAll')} onAction={() => router.push('/book')} />
            {popular.map((l) => (
              <ListingRow key={l.id} listing={l} onPress={() => openPartner(l.id, 'explore', prefs.anonymousId)} />
            ))}
          </View>
        </>
      )}

      <NearMeSheet
        visible={nearMeOpen}
        onClose={() => setNearMeOpen(false)}
        onChooseCity={(id) => {
          setNearMeOpen(false);
          update({ tripStage: prefs.tripStage ?? 'in_morocco' });
          openDestination(id);
        }}
      />
    </Screen>
  );
}

/** Explains location use before any permission prompt; always offers a manual city. */
function NearMeSheet({
  visible,
  onClose,
  onChooseCity,
}: {
  visible: boolean;
  onClose: () => void;
  onChooseCity: (id: string) => void;
}) {
  const { t, colors, locale } = useApp();
  const [locating, setLocating] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const locate = async () => {
    setLocating(true);
    setMessage(null);
    track('location_permission_requested');
    try {
      const permission = await Location.requestForegroundPermissionsAsync();
      track('location_permission_result', { properties: { granted: permission.granted } });
      if (!permission.granted) {
        setMessage(t('explore.locationDenied'));
        return;
      }
      const position = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
      // Only the nearest city is used; the position itself is not stored or sent.
      const nearest = byDistance({ lat: position.coords.latitude, lng: position.coords.longitude }, catalog.destinations)[0];
      if (!nearest || nearest.km > OUTSIDE_KM) {
        setMessage(t('explore.locationOutside'));
        return;
      }
      onChooseCity(nearest.id);
    } catch {
      setMessage(t('explore.locationError'));
    } finally {
      setLocating(false);
    }
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose} accessibilityLabel={t('common.cancel')} />
      <View style={[styles.sheet, { backgroundColor: colors.background }]}>
        <T variant="title">{t('explore.locationWhyTitle')}</T>
        <T tone="muted">{t('explore.locationWhy')}</T>
        <Button label={t('explore.useMyLocation')} icon="navigate" onPress={locate} loading={locating} />
        {message ? <T tone="warning">{message}</T> : null}
        <T variant="heading">{t('explore.chooseManually')}</T>
        <Row style={{ flexWrap: 'wrap' }}>
          {catalog.destinations.map((d) => (
            <Chip key={d.id} label={destinationName(d, locale)} onPress={() => onChooseCity(d.id)} />
          ))}
        </Row>
        <Button label={t('common.cancel')} kind="ghost" onPress={onClose} />
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  search: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    borderWidth: 1,
    borderRadius: 999,
    paddingHorizontal: spacing.lg,
    minHeight: 48,
  },
  searchInput: { flex: 1, fontSize: 16, paddingVertical: spacing.sm },
  backdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.35)' },
  sheet: {
    padding: spacing.xl,
    gap: spacing.md,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    maxWidth: 720,
    width: '100%',
    alignSelf: 'center',
  },
});
