/**
 * Photos shown with an AI answer (Unsplash). Unsplash requires the credit
 * wherever a photo appears: the photographer and Unsplash, both linked.
 */
import type { Photo } from '@comemorocco/shared';
import { radii, spacing } from '@comemorocco/ui';
import { Image } from 'expo-image';
import * as WebBrowser from 'expo-web-browser';
import { Pressable, ScrollView, View } from 'react-native';

import { useApp } from '@/lib/app-state';

import { T } from './ui';

export function PhotoStrip({ photos }: { photos: Photo[] }) {
  const { colors, t } = useApp();
  if (!photos.length) return null;
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: spacing.sm }}>
      {photos.map((photo) => (
        <View key={photo.url} style={{ width: 240, gap: 4 }}>
          <Pressable onPress={() => WebBrowser.openBrowserAsync(photo.source_url)} accessibilityRole="link" accessibilityLabel={photo.alt || photo.photographer}>
            <Image
              source={photo.url}
              placeholder={photo.thumb_url}
              style={{ width: 240, height: 160, borderRadius: radii.md, backgroundColor: colors.surfaceAlt }}
              contentFit="cover"
              transition={200}
            />
          </Pressable>
          <T variant="caption" tone="muted" numberOfLines={1}>
            {t('ai.photoBy')}{' '}
            <T variant="caption" tone="secondary" onPress={() => WebBrowser.openBrowserAsync(photo.photographer_url)}>
              {photo.photographer}
            </T>{' '}
            ·{' '}
            <T variant="caption" tone="secondary" onPress={() => WebBrowser.openBrowserAsync(photo.source_url)}>
              Unsplash
            </T>
          </T>
        </View>
      ))}
    </ScrollView>
  );
}
