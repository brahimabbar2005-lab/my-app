/**
 * Moderation queue (Master Plan §29). Shown only to accounts in admin_users;
 * the database checks again on every call, so opening this route without
 * being an admin shows nothing. Staff tool: English only.
 */
import { spacing } from '@comemorocco/ui';
import { router, useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { ActivityIndicator, TextInput, View } from 'react-native';

import { PostAge } from '@/components/community';
import { Button, Card, EmptyState, Pill, Row, Screen, T } from '@/components/ui';
import { useApp } from '@/lib/app-state';
import { fetchQueue, isAdmin, moderate, type ModerationAction, type QueueItem } from '@/lib/community';

export default function Admin() {
  const { colors } = useApp();
  const [allowed, setAllowed] = useState<boolean | null>(null);
  const [items, setItems] = useState<QueueItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [reason, setReason] = useState('');

  const load = useCallback(async () => {
    const admin = await isAdmin();
    setAllowed(admin);
    if (!admin) return;
    const result = await fetchQueue();
    if (result.data) {
      setItems(result.data);
      setError(null);
    } else setError(result.error ?? 'error');
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  const act = async (item: QueueItem, action: ModerationAction) => {
    setBusy(`${item.target_id}:${action}`);
    const target = action === 'suspend' ? { type: 'user' as const, id: item.author_id } : { type: item.target_type, id: item.target_id };
    const result = await moderate(target, action, reason);
    setBusy(null);
    if (result.error) setError(result.error);
    else {
      setReason('');
      load();
    }
  };

  if (allowed === null) return <ActivityIndicator style={{ marginTop: spacing.xl }} />;
  if (!allowed) {
    return (
      <Screen edges={['bottom']}>
        <EmptyState icon="lock-closed-outline" title="Moderators only" />
      </Screen>
    );
  }

  return (
    <Screen edges={['bottom']}>
      <T tone="muted">
        Posts and replies with open reports, or held by the automatic checks. Every action is recorded in the audit log.
      </T>
      <TextInput
        value={reason}
        onChangeText={setReason}
        placeholder="Reason for the next action (optional, kept in the audit log)"
        placeholderTextColor={colors.textMuted}
        accessibilityLabel="Moderation reason"
        style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 12, padding: spacing.md, color: colors.text }}
      />
      {error ? <T tone="error">{error}</T> : null}
      {items === null ? (
        <ActivityIndicator style={{ marginTop: spacing.xl }} />
      ) : items.length === 0 ? (
        <EmptyState icon="checkmark-done-outline" title="Nothing to review." />
      ) : (
        items.map((item) => (
          <Card key={item.target_id}>
            <Row style={{ gap: spacing.xs, flexWrap: 'wrap' }}>
              <Pill label={item.target_type} tone="accent" />
              <Pill label={item.status} tone={item.status === 'published' ? 'muted' : 'warning'} />
              {item.open_reports ? <Pill label={`${item.open_reports} report(s)`} tone="warning" /> : null}
              {[...item.report_reasons, ...item.flag_reasons].map((r) => (
                <Pill key={r} label={r.replace('_', ' ')} />
              ))}
            </Row>
            {item.title ? <T variant="heading">{item.title}</T> : null}
            <T numberOfLines={6}>{item.body}</T>
            <T variant="caption" tone="muted">
              <PostAge iso={item.last_activity} /> · author {item.author_id.slice(0, 8)}
            </T>
            <Row style={{ flexWrap: 'wrap', gap: spacing.sm }}>
              <ActionButton label="Restore" icon="checkmark-circle-outline" busy={busy === `${item.target_id}:restore`} onPress={() => act(item, 'restore')} />
              <ActionButton label="Hide" icon="eye-off-outline" busy={busy === `${item.target_id}:hide`} onPress={() => act(item, 'hide')} />
              <ActionButton label="Remove" icon="trash-outline" danger busy={busy === `${item.target_id}:remove`} onPress={() => act(item, 'remove')} />
              <ActionButton label="Suspend author 7 days" icon="ban-outline" danger busy={busy === `${item.target_id}:suspend`} onPress={() => act(item, 'suspend')} />
            </Row>
            {item.target_type === 'post' ? (
              <Button label="Open post" kind="ghost" icon="open-outline" onPress={() => router.push(`/community/${item.target_id}`)} />
            ) : null}
          </Card>
        ))
      )}
    </Screen>
  );
}

function ActionButton({
  label,
  icon,
  onPress,
  busy,
  danger,
}: {
  label: string;
  icon: 'checkmark-circle-outline' | 'eye-off-outline' | 'trash-outline' | 'ban-outline';
  onPress: () => void;
  busy: boolean;
  danger?: boolean;
}) {
  return (
    <View style={{ flexGrow: 1 }}>
      <Button label={label} icon={icon} kind={danger ? 'danger' : 'secondary'} onPress={onPress} loading={busy} />
    </View>
  );
}
