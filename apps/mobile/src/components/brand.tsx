/**
 * Moroccan identity, used sparingly (Master Plan §42, §46): an eight-point
 * zellige star made from two rotated squares — no image assets — and
 * destination tiles that will carry photography once the content layer
 * serves WordPress featured images.
 */
import { radii, spacing } from '@comemorocco/ui';
import Ionicons from '@expo/vector-icons/Ionicons';
import { Image } from 'expo-image';
import { Pressable, StyleSheet, View, type ViewStyle } from 'react-native';

import { type Destination, destinationName, destinationTagline, type Listing } from '@/data/catalog';
import { pageImage } from '@/data/images';
import { useApp } from '@/lib/app-state';

import { AddToTripButton, SaveButton } from './trip-buttons';
import { Card, Pill, Row, T } from './ui';

export function ZelligeStar({
  size,
  color,
  opacity = 1,
  style,
}: {
  size: number;
  color: string;
  opacity?: number;
  style?: ViewStyle;
}) {
  const square = size / Math.SQRT2;
  const base: ViewStyle = { position: 'absolute', width: square, height: square, backgroundColor: color };
  // Opacity on the container, not the fill, so the two squares read as one star.
  return (
    <View
      pointerEvents="none"
      style={[{ width: size, height: size, alignItems: 'center', justifyContent: 'center', opacity }, style]}>
      <View style={base} />
      <View style={[base, { transform: [{ rotate: '45deg' }] }]} />
    </View>
  );
}

export function DestinationTile({
  destination,
  onPress,
  width = 160,
}: {
  destination: Destination;
  onPress: () => void;
  width?: number;
}) {
  const { locale } = useApp();
  const name = destinationName(destination, locale);
  const photo = pageImage(destination.guide_url);
  // The heart sits beside the tile's pressable, not inside it: nested
  // buttons are invalid on web and confuse screen readers.
  return (
    <View style={{ width }}>
      <Pressable
        onPress={onPress}
        accessibilityRole="button"
        accessibilityLabel={name}
        style={({ pressed }) => [styles.tile, { backgroundColor: destination.hue, opacity: pressed ? 0.9 : 1 }]}>
        {photo ? (
          <>
            <Image source={photo} style={StyleSheet.absoluteFill} contentFit="cover" transition={200} accessible={false} />
            {/* Keeps the white text readable on any photo. */}
            <View style={[StyleSheet.absoluteFill, styles.tileShade]} />
          </>
        ) : (
          <>
            <ZelligeStar size={width * 0.9} color="#FFFFFF" opacity={0.12} style={styles.tileStar} />
            <ZelligeStar size={width * 0.35} color="#FFFFFF" opacity={0.2} style={styles.tileStarSmall} />
          </>
        )}
        <View style={styles.tileText}>
          <T variant="bodyStrong" style={{ color: '#FFFFFF' }} numberOfLines={2}>
            {name}
          </T>
          <T variant="caption" style={{ color: 'rgba(255,255,255,0.9)' }} numberOfLines={2}>
            {destinationTagline(destination, locale)}
          </T>
        </View>
      </Pressable>
      <View style={styles.tileHeart}>
        <SaveButton refType="destination" refId={destination.id} title={name} onDark />
      </View>
    </View>
  );
}

const CATEGORY_ICON: Record<Listing['category'], keyof typeof Ionicons.glyphMap> = {
  stay: 'bed-outline',
  experience: 'compass-outline',
  car: 'car-outline',
  transfer: 'airplane-outline',
  driver: 'person-outline',
};

export function ListingRow({ listing, onPress }: { listing: Listing; onPress: () => void }) {
  const { colors, t } = useApp();
  return (
    <Card>
      <Row style={{ alignItems: 'flex-start', gap: spacing.md }}>
        <View style={[styles.listingIcon, { backgroundColor: colors.surfaceAlt }]}>
          <Ionicons name={CATEGORY_ICON[listing.category]} size={22} color={colors.primary} />
        </View>
        <View style={{ flex: 1, gap: spacing.xs }}>
          <T variant="bodyStrong" numberOfLines={2}>
            {listing.title}
          </T>
          <Row style={{ flexWrap: 'wrap' }}>
            <Pill label={listing.subtitle} />
            {listing.partner !== listing.title ? (
              <T variant="caption" tone="muted">
                {listing.partner}
              </T>
            ) : null}
          </Row>
        </View>
        <SaveButton refType="listing" refId={listing.id} title={listing.title} />
      </Row>
      {listing.destination ? (
        <AddToTripButton item={{ type: 'listing', refId: listing.id, title: listing.title }} />
      ) : null}
      <Row style={{ justifyContent: 'space-between' }}>
        <T variant="caption" tone="muted" style={{ flex: 1 }}>
          {t('common.sponsored')} · {t('book.priceIndicative')}
        </T>
        <Pressable
          onPress={onPress}
          accessibilityRole="link"
          style={({ pressed }) => [styles.cta, { backgroundColor: colors.primary, opacity: pressed ? 0.85 : 1 }]}>
          <T variant="label" tone="onPrimary">
            {t('book.viewOptions')}
          </T>
          <Ionicons name="open-outline" size={14} color={colors.onPrimary} />
        </Pressable>
      </Row>
    </Card>
  );
}

export function ArticleCard({
  title,
  excerpt,
  url,
  onPress,
  width,
}: {
  title: string;
  excerpt?: string;
  /** The article's page; its photo is shown when we have one. */
  url?: string;
  onPress: () => void;
  width?: number;
}) {
  const { colors, t } = useApp();
  const photo = pageImage(url);
  return (
    <Pressable onPress={onPress} accessibilityRole="link" style={({ pressed }) => [{ width, opacity: pressed ? 0.85 : 1 }]}>
      <Card style={{ height: '100%' }}>
        {photo ? (
          <Image
            source={photo}
            style={[styles.articlePhoto, { backgroundColor: colors.surfaceAlt }]}
            contentFit="cover"
            transition={200}
            accessible={false}
          />
        ) : null}
        <Row>
          <ZelligeStar size={14} color={colors.accent} />
          <T variant="label" tone="muted">
            comemorocco.com
          </T>
        </Row>
        <T variant="bodyStrong" numberOfLines={3}>
          {title}
        </T>
        {excerpt ? (
          <T variant="caption" tone="muted" numberOfLines={3}>
            {excerpt}
          </T>
        ) : null}
        <T variant="caption" tone="secondary" style={{ marginTop: 'auto' }}>
          {t('common.readFullGuide')} →
        </T>
      </Card>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  tile: { height: 200, borderRadius: radii.lg, overflow: 'hidden', justifyContent: 'flex-end' },
  tileStar: { position: 'absolute', top: -30, end: -40 },
  tileStarSmall: { position: 'absolute', top: 24, start: 16 },
  tileText: { padding: spacing.md, gap: 2 },
  tileShade: { backgroundColor: 'rgba(0,0,0,0.35)' },
  articlePhoto: { height: 130, borderRadius: radii.md },
  tileHeart: { position: 'absolute', top: spacing.md, end: spacing.md },
  listingIcon: { width: 44, height: 44, borderRadius: radii.md, alignItems: 'center', justifyContent: 'center' },
  cta: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radii.pill,
  },
});
