/** One community post with its replies, votes, report and block. */
import { spacing } from '@comemorocco/ui';
import { router, Stack, useFocusEffect, useLocalSearchParams } from 'expo-router';
import { useCallback, useState } from 'react';
import { ActivityIndicator, TextInput, View } from 'react-native';

import { PostAge, ReportSheet } from '@/components/community';
import { Button, Card, EmptyState, Pill, Row, Screen, T } from '@/components/ui';
import { destinationName, getDestination } from '@/data/catalog';
import { track } from '@/lib/analytics';
import { useApp } from '@/lib/app-state';
import { useAuth } from '@/lib/auth';
import { addComment, blockUser, type Comment, type FeedPost, fetchPost, report, vote } from '@/lib/community';

type Target = { type: 'post' | 'comment'; id: string };

export default function PostScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { t, locale, colors } = useApp();
  const { userId } = useAuth();
  const [post, setPost] = useState<FeedPost | null>(null);
  const [comments, setComments] = useState<Comment[]>([]);
  const [myVote, setMyVote] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [reply, setReply] = useState('');
  const [sending, setSending] = useState(false);
  const [reporting, setReporting] = useState<Target | null>(null);
  const [confirmBlock, setConfirmBlock] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    const result = await fetchPost(id);
    if (!result.data) {
      setError(result.error ?? 'error');
      return;
    }
    setError(null);
    setPost(result.data.post);
    setComments(result.data.comments);
    setMyVote(result.data.myVote);
  }, [id]);

  // Load on focus, so returning from sign-in shows the signed-in view.
  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  const needAccount = () => router.push('/sign-in');

  const onVote = async (value: 1 | -1) => {
    if (!userId || !post) return needAccount();
    const next = myVote === value ? 0 : value;
    setPost({ ...post, score: post.score - myVote + next });
    setMyVote(next);
    const result = await vote(userId, post.id, next);
    if (result.error) load();
  };

  const onReply = async () => {
    if (!userId || !post) return needAccount();
    setSending(true);
    const result = await addComment(userId, post.id, reply);
    setSending(false);
    if (!result.data) {
      setNotice(result.error ?? null);
      return;
    }
    setReply('');
    if (result.data === 'pending') setNotice(t('community.held'));
    track('community_comment_created', { properties: { status: result.data } });
    load();
  };

  const onBlock = async (authorId: string) => {
    if (!userId) return needAccount();
    await blockUser(userId, authorId);
    setConfirmBlock(null);
    track('user_blocked');
    if (authorId === post?.author_id) router.back();
    else {
      setNotice(t('community.blocked'));
      load();
    }
  };

  if (error) {
    return (
      <Screen edges={['bottom']}>
        <EmptyState icon="alert-circle-outline" title={t('community.loadError')}>
          <Button label={t('common.retry')} kind="secondary" onPress={load} />
        </EmptyState>
      </Screen>
    );
  }
  if (!post) return <ActivityIndicator style={{ marginTop: spacing.xl }} />;

  const place = post.destination_id ? getDestination(post.destination_id) : undefined;
  const mine = post.author_id === userId;

  return (
    <Screen edges={['bottom']}>
      <Stack.Screen options={{ title: t(`community.kind_${post.kind}`) }} />
      <Row style={{ gap: spacing.xs, flexWrap: 'wrap' }}>
        <Pill label={t(`community.kind_${post.kind}`)} tone="accent" />
        {place ? <Pill label={destinationName(place, locale)} /> : null}
        {post.status === 'pending' ? <Pill label={t('community.inReview')} tone="warning" /> : null}
        {post.status === 'hidden' ? <Pill label={t('community.hiddenBadge')} tone="warning" /> : null}
      </Row>
      <T variant="title">{post.title}</T>
      <T variant="caption" tone="muted">
        {mine ? t('community.you') : post.author_name || t('community.traveller')} · <PostAge iso={post.created_at} />
      </T>
      <T>{post.body}</T>

      <Row style={{ gap: spacing.sm }}>
        <View style={{ flex: 1 }}>
          <Button
            label={`${t('community.upvote')} · ${post.score}`}
            icon={myVote === 1 ? 'arrow-up-circle' : 'arrow-up-circle-outline'}
            kind={myVote === 1 ? 'primary' : 'secondary'}
            onPress={() => onVote(1)}
          />
        </View>
        <View style={{ flex: 1 }}>
          <Button
            label={t('community.downvote')}
            icon={myVote === -1 ? 'arrow-down-circle' : 'arrow-down-circle-outline'}
            kind={myVote === -1 ? 'primary' : 'secondary'}
            onPress={() => onVote(-1)}
          />
        </View>
      </Row>

      {!mine ? (
        <Row style={{ gap: spacing.sm }}>
          <View style={{ flex: 1 }}>
            <Button
              label={t('community.report')}
              icon="flag-outline"
              kind="ghost"
              onPress={() => (userId ? setReporting({ type: 'post', id: post.id }) : needAccount())}
            />
          </View>
          <View style={{ flex: 1 }}>
            <Button
              label={t('community.block')}
              icon="ban-outline"
              kind="ghost"
              onPress={() => (userId ? setConfirmBlock(post.author_id) : needAccount())}
            />
          </View>
        </Row>
      ) : null}

      {confirmBlock ? (
        <Card style={{ borderColor: colors.error }}>
          <T>{t('community.blockConfirm')}</T>
          <Row>
            <View style={{ flex: 1 }}>
              <Button label={t('common.cancel')} kind="secondary" onPress={() => setConfirmBlock(null)} />
            </View>
            <View style={{ flex: 1 }}>
              <Button label={t('community.block')} kind="danger" onPress={() => onBlock(confirmBlock)} />
            </View>
          </Row>
        </Card>
      ) : null}

      {notice ? <T tone="success">{notice}</T> : null}

      <T variant="heading">
        {t('community.comments')} · {comments.length}
      </T>
      {comments.length === 0 ? <T tone="muted">{t('community.noComments')}</T> : null}
      {comments.map((c) => (
        <Card key={c.id}>
          <Row style={{ justifyContent: 'space-between' }}>
            <T variant="caption" tone="muted" style={{ flex: 1 }}>
              {c.author_id === userId ? t('community.you') : c.author_name || t('community.traveller')} · <PostAge iso={c.created_at} />
            </T>
            {c.status === 'pending' ? <Pill label={t('community.inReview')} tone="warning" /> : null}
          </Row>
          <T>{c.body}</T>
          {c.author_id !== userId ? (
            <Row style={{ gap: spacing.sm }}>
              <Button
                label={t('community.report')}
                icon="flag-outline"
                kind="ghost"
                onPress={() => (userId ? setReporting({ type: 'comment', id: c.id }) : needAccount())}
              />
              <Button
                label={t('community.block')}
                icon="ban-outline"
                kind="ghost"
                onPress={() => (userId ? setConfirmBlock(c.author_id) : needAccount())}
              />
            </Row>
          ) : null}
        </Card>
      ))}

      {userId ? (
        <Card>
          <TextInput
            value={reply}
            onChangeText={setReply}
            placeholder={t('community.commentPlaceholder')}
            placeholderTextColor={colors.textMuted}
            multiline
            maxLength={5000}
            accessibilityLabel={t('community.commentPlaceholder')}
            style={{ minHeight: 64, color: colors.text, textAlignVertical: 'top' }}
          />
          <Button label={t('community.reply')} icon="send-outline" onPress={onReply} loading={sending} disabled={!reply.trim()} />
        </Card>
      ) : (
        <Button label={t('common.signIn')} icon="person-outline" kind="secondary" onPress={needAccount} />
      )}

      <ReportSheet
        visible={!!reporting}
        onClose={() => setReporting(null)}
        onSubmit={async (reason, details) => {
          if (!userId || !reporting) return;
          const result = await report(userId, reporting, reason, details);
          track('content_reported', { properties: { target_type: reporting.type, reason } });
          setNotice(result.data === 'already' ? t('community.reportAlready') : result.error ?? t('community.reportSent'));
        }}
      />
    </Screen>
  );
}
