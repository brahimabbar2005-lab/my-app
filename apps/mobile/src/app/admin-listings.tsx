/**
 * Admin: every offer in the catalogue (drafts and archived included), to add
 * hotels, riads, hostels, tours… or edit them. Staff tool: English only.
 */
import { spacing } from '@comemorocco/ui';
import { router, useFocusEffect } from 'expo-router';
import { useCallback, useMemo, useState } from 'react';
import { ActivityIndicator, Pressable, TextInput } from 'react-native';

import { Button, Card, Chip, EmptyState, Pill, Row, Screen, T } from '@/components/ui';
import { getDestination } from '@/data/catalog';
import { type AdminListing, fetchAdminListings, type ListingStatus } from '@/lib/admin-catalog';
import { useApp } from '@/lib/app-state';
import { isAdmin } from '@/lib/community';

const STATUSES: (ListingStatus | 'all')[] = ['all', 'published', 'draft', 'archived'];

export default function AdminListings() {
  const { colors } = useApp();
  const [allowed, setAllowed] = useState<boolean | null>(null);
  const [rows, setRows] = useState<AdminListing[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState<ListingStatus | 'all'>('all');

  const load = useCallback(async () => {
    const admin = await isAdmin();
    setAllowed(admin);
    if (!admin) return;
    const result = await fetchAdminListings();
    if (result.data) setRows(result.data);
    else setError(result.error ?? 'error');
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (rows ?? []).filter(
      (r) =>
        (status === 'all' || r.status === status) &&
        (!q || `${r.title} ${r.partner_name ?? ''} ${r.destination_id ?? ''} ${r.subtype ?? ''}`.toLowerCase().includes(q)),
    );
  }, [rows, query, status]);

  if (allowed === null) return <ActivityIndicator style={{ marginTop: spacing.xl }} />;
  if (!allowed) {
    return (
      <Screen edges={['bottom']}>
        <EmptyState icon="lock-closed-outline" title="Admins only" />
      </Screen>
    );
  }

  return (
    <Screen edges={['bottom']}>
      <Button label="Add an offer" icon="add-circle-outline" onPress={() => router.push('/admin-listing')} />
      <TextInput
        value={query}
        onChangeText={setQuery}
        placeholder="Search by name, city, type or partner"
        placeholderTextColor={colors.textMuted}
        accessibilityLabel="Search offers"
        style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 12, padding: spacing.md, color: colors.text }}
      />
      <Row style={{ flexWrap: 'wrap' }}>
        {STATUSES.map((s) => (
          <Chip key={s} label={s} selected={status === s} onPress={() => setStatus(s)} />
        ))}
      </Row>
      {error ? <T tone="error">{error}</T> : null}
      {rows === null ? (
        <ActivityIndicator />
      ) : (
        <>
          <T variant="caption" tone="muted">
            {shown.length} of {rows.length} offers
          </T>
          {shown.map((r) => (
            <Pressable key={r.id} onPress={() => router.push({ pathname: '/admin-listing', params: { id: r.id } })} accessibilityRole="button">
              <Card>
                <Row style={{ flexWrap: 'wrap', gap: spacing.xs }}>
                  <Pill label={r.status} tone={r.status === 'published' ? 'accent' : 'warning'} />
                  <Pill label={r.subtype ?? r.category} />
                  {r.destination_id ? <Pill label={getDestination(r.destination_id)?.name.en ?? r.destination_id} /> : null}
                  {r.partner_url ? <Pill label="partner link" /> : r.website_url ? <Pill label="direct link" /> : <Pill label="no link" tone="warning" />}
                </Row>
                <T variant="bodyStrong">{r.title}</T>
                <T variant="caption" tone="muted">
                  {r.id} · {r.partner_name || '—'}
                </T>
              </Card>
            </Pressable>
          ))}
        </>
      )}
    </Screen>
  );
}
