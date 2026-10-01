/**
 * Community (Master Plan §28–29). Guests can read; posting, replying, voting
 * and reporting need an account. No sample posts are shown: invented
 * traveller experiences would be fabricated reviews.
 */
import { spacing } from '@comemorocco/ui';
import { Ionicons } from '@expo/vector-icons';
import { router, useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, View } from 'react-native';

import { DestinationChips, PostAge } from '@/components/community';
import { Button, Card, Chip, EmptyState, Pill, Row, Screen, T } from '@/components/ui';
import { destinationName, getDestination } from '@/data/catalog';
import { useApp } from '@/lib/app-state';
import { useAuth } from '@/lib/auth';
import { type FeedPost, fetchFeed, POST_KINDS, type PostKind } from '@/lib/community';
import { supabase } from '@/lib/supabase';

const GUIDELINES = [
  'Share real, first-hand experiences.',
  'Be respectful of other travellers and of Moroccans.',
  'No personal attacks, hate, or naming private individuals.',
  'Report behaviour, not people: describe what happened, where and when.',
  'No spam, self-promotion or undisclosed paid content.',
];

export default function Community() {
  const { t } = useApp();
  const { userId } = useAuth();
  const [kind, setKind] = useState<PostKind | null>(null);
  const [destination, setDestination] = useState<string | null>(null);
  const [posts, setPosts] = useState<FeedPost[] | null>(null);
  const [error, setError] = useState(false);

  const load = useCallback(async () => {
    if (!supabase) return;
    setError(false);
    const result = await fetchFeed({ kind, destination, viewer: userId });
    if (result.data) setPosts(result.data);
    else setError(true);
  }, [kind, destination, userId]);

  // Reload whenever the tab is shown (after posting, reporting or blocking).
  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  const compose = () => router.push(userId ? '/community/new' : '/sign-in');

  return (
    <Screen edges={[]}>
      <Row style={{ justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <View style={{ gap: spacing.xs, flex: 1 }}>
          <T variant="title">{t('community.title')}</T>
          <T tone="muted">{t('community.subtitle')}</T>
        </View>
      </Row>

      {!supabase ? (
        <EmptyState icon="people-outline" title={t('community.notConfigured')} />
      ) : (
        <>
          <Button label={t('community.ask')} icon="create-outline" onPress={compose} />
          {!userId ? (
            <T variant="caption" tone="muted" style={{ textAlign: 'center' }}>
              {t('community.signInToPost')}
            </T>
          ) : null}

          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: spacing.sm }}>
            <Chip label={t('community.all')} selected={!kind} onPress={() => setKind(null)} />
            {POST_KINDS.map((k) => (
              <Chip key={k} label={t(`community.kind_${k}`)} selected={kind === k} onPress={() => setKind(k)} />
            ))}
          </ScrollView>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: spacing.sm }}>
            <Chip
              label={t('community.anyDestination')}
              icon="globe-outline"
              selected={!destination}
              onPress={() => setDestination(null)}
            />
            <DestinationChips selected={destination} onSelect={setDestination} />
          </ScrollView>

          {error ? (
            <EmptyState icon="cloud-offline-outline" title={t('community.loadError')}>
              <Button label={t('common.retry')} kind="secondary" onPress={load} />
            </EmptyState>
          ) : posts === null ? (
            <ActivityIndicator style={{ marginVertical: spacing.xl }} />
          ) : posts.length === 0 ? (
            <EmptyState icon="chatbubbles-outline" title={t('community.empty')} />
          ) : (
            posts.map((post) => <PostCard key={post.id} post={post} mine={post.author_id === userId} />)
          )}
        </>
      )}

      <Card>
        <T variant="heading">{t('community.guidelines')}</T>
        {GUIDELINES.map((g) => (
          <Row key={g} style={{ alignItems: 'flex-start' }}>
            <T>•</T>
            <T style={{ flex: 1 }}>{g}</T>
          </Row>
        ))}
      </Card>
    </Screen>
  );
}

function PostCard({ post, mine }: { post: FeedPost; mine: boolean }) {
  const { t, locale, colors } = useApp();
  const place = post.destination_id ? getDestination(post.destination_id) : undefined;
  return (
    <Pressable
      onPress={() => router.push(`/community/${post.id}`)}
      accessibilityRole="button"
      accessibilityLabel={post.title}
      style={({ pressed }) => ({ opacity: pressed ? 0.85 : 1 })}>
      <Card>
        <Row style={{ gap: spacing.xs, flexWrap: 'wrap' }}>
          <Pill label={t(`community.kind_${post.kind}`)} tone="accent" />
          {place ? <Pill label={destinationName(place, locale)} /> : null}
          {post.status === 'pending' ? <Pill label={t('community.inReview')} tone="warning" /> : null}
          {post.status === 'hidden' ? <Pill label={t('community.hiddenBadge')} tone="warning" /> : null}
        </Row>
        <T variant="heading" numberOfLines={2}>
          {post.title}
        </T>
        <T tone="muted" numberOfLines={3}>
          {post.body}
        </T>
        <Row style={{ gap: spacing.md }}>
          <T variant="caption" tone="muted" style={{ flex: 1 }} numberOfLines={1}>
            {mine ? t('community.you') : post.author_name || t('community.traveller')} · <PostAge iso={post.created_at} />
          </T>
          <Row style={{ gap: 4 }}>
            <Ionicons name="arrow-up-outline" size={16} color={colors.textMuted} />
            <T variant="caption" tone="muted">
              {post.score}
            </T>
          </Row>
          <Row style={{ gap: 4 }}>
            <Ionicons name="chatbubble-outline" size={15} color={colors.textMuted} />
            <T variant="caption" tone="muted">
              {post.comment_count}
            </T>
          </Row>
        </Row>
      </Card>
    </Pressable>
  );
}
