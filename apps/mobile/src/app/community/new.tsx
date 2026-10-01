/** Write a community post. Needs an account; the database screens every post. */
import { spacing } from '@comemorocco/ui';
import { router } from 'expo-router';
import { useState } from 'react';
import { ScrollView, TextInput, View } from 'react-native';

import { DestinationChips } from '@/components/community';
import { Button, Chip, EmptyState, Screen, T } from '@/components/ui';
import { track } from '@/lib/analytics';
import { useApp } from '@/lib/app-state';
import { useAuth } from '@/lib/auth';
import { createPost, POST_KINDS, type PostDraft, validateDraft } from '@/lib/community';

export default function NewPost() {
  const { t, colors } = useApp();
  const { userId } = useAuth();
  const [draft, setDraft] = useState<PostDraft>({ kind: 'question', destination_id: null, title: '', body: '' });
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ tone: 'error' | 'success'; text: string } | null>(null);

  if (!userId) {
    return (
      <Screen edges={['bottom']}>
        <EmptyState icon="person-outline" title={t('community.signInToPost')}>
          <Button label={t('common.signIn')} onPress={() => router.replace('/sign-in')} />
        </EmptyState>
      </Screen>
    );
  }

  const set = (patch: Partial<PostDraft>) => {
    setDraft((d) => ({ ...d, ...patch }));
    setMessage(null);
  };

  const input = {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    padding: spacing.md,
    fontSize: 16,
    color: colors.text,
  } as const;

  const publish = async () => {
    const problem = validateDraft(draft);
    if (problem) {
      setMessage({ tone: 'error', text: t(`community.problem_${problem}`) });
      return;
    }
    setBusy(true);
    const result = await createPost(userId, draft);
    setBusy(false);
    if (!result.data) {
      setMessage({ tone: 'error', text: result.error ?? '' });
      return;
    }
    track('community_post_created', {
      ...(draft.destination_id ? { destination: draft.destination_id } : {}),
      properties: { kind: draft.kind, status: result.data.status },
    });
    if (result.data.status === 'pending') {
      setMessage({ tone: 'success', text: t('community.held') });
      return;
    }
    router.replace(`/community/${result.data.id}`);
  };

  return (
    <Screen edges={['bottom']}>
      <T variant="label">{t('community.kindLabel')}</T>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm }}>
        {POST_KINDS.map((k) => (
          <Chip key={k} label={t(`community.kind_${k}`)} selected={draft.kind === k} onPress={() => set({ kind: k })} />
        ))}
      </View>

      <T variant="label">{t('community.destinationLabel')}</T>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: spacing.sm }}>
        <Chip
          label={t('community.anyDestination')}
          icon="globe-outline"
          selected={!draft.destination_id}
          onPress={() => set({ destination_id: null })}
        />
        <DestinationChips selected={draft.destination_id} onSelect={(id) => set({ destination_id: id })} />
      </ScrollView>

      <T variant="label">{t('community.titleLabel')}</T>
      <TextInput
        value={draft.title}
        onChangeText={(title) => set({ title })}
        placeholder={t('community.titlePlaceholder')}
        placeholderTextColor={colors.textMuted}
        maxLength={160}
        accessibilityLabel={t('community.titleLabel')}
        style={input}
      />

      <T variant="label">{t('community.bodyLabel')}</T>
      <TextInput
        value={draft.body}
        onChangeText={(body) => set({ body })}
        placeholder={t('community.bodyPlaceholder')}
        placeholderTextColor={colors.textMuted}
        multiline
        maxLength={10000}
        accessibilityLabel={t('community.bodyLabel')}
        style={[input, { minHeight: 160, textAlignVertical: 'top' }]}
      />

      {message ? <T tone={message.tone}>{message.text}</T> : null}
      {message?.tone === 'success' ? (
        <Button label={t('community.title')} icon="arrow-back-outline" kind="secondary" onPress={() => router.back()} />
      ) : (
        <Button label={t('community.publish')} icon="send-outline" onPress={publish} loading={busy} />
      )}
    </Screen>
  );
}
