/**
 * Admin: add or edit one offer (hotel, riad, hostel, tour, car…). Partner
 * links are stored privately and opened through the tracked /go redirect;
 * direct links (the riad's own booking page) are public. Staff tool: English.
 */
import { spacing } from '@comemorocco/ui';
import { Image } from 'expo-image';
import { router, Stack, useLocalSearchParams } from 'expo-router';
import { type ReactNode, useEffect, useState } from 'react';
import { ActivityIndicator, ScrollView, Switch, TextInput, View } from 'react-native';

import { Button, Chip, Row, Screen, T } from '@/components/ui';
import { catalog, type ListingCategory, type ListingSubtype } from '@/data/catalog';
import {
  checkDraft,
  type DraftProblem,
  EMPTY_DRAFT,
  fetchAdminListings,
  type ListingDraft,
  type ListingStatus,
  saveListing,
  toDraft,
} from '@/lib/admin-catalog';
import { useApp } from '@/lib/app-state';
import { refreshListings } from '@/lib/listings';

const CATEGORIES: ListingCategory[] = ['stay', 'experience', 'car', 'transfer', 'driver'];
const SUBTYPES: Record<ListingCategory, ListingSubtype[]> = {
  stay: ['hotel', 'riad', 'hostel', 'guesthouse', 'camp', 'apartment', 'villa'],
  experience: ['tour', 'day_trip', 'activity', 'class'],
  car: ['car'],
  transfer: ['transfer'],
  driver: ['driver'],
};
const STATUSES: ListingStatus[] = ['draft', 'published', 'archived'];
const PROBLEMS: Record<DraftProblem, string> = {
  title: 'Add a name (at least 3 characters).',
  price: 'Price: whole dirhams, digits only.',
  image: 'Photo address must start with https://',
  link: 'Booking link must start with https://',
};

export default function AdminListing() {
  const { id } = useLocalSearchParams<{ id?: string }>();
  const { colors } = useApp();
  const [draft, setDraft] = useState<ListingDraft | null>(id ? null : EMPTY_DRAFT);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    let alive = true;
    fetchAdminListings().then((result) => {
      if (!alive) return;
      const row = result.data?.find((r) => r.id === id);
      if (row) setDraft(toDraft(row));
      else setMessage(result.error ?? 'Offer not found.');
    });
    return () => {
      alive = false;
    };
  }, [id]);

  if (!draft) {
    return message ? (
      <Screen edges={['bottom']}>
        <T tone="error">{message}</T>
      </Screen>
    ) : (
      <ActivityIndicator style={{ marginTop: spacing.xl }} />
    );
  }

  const set = (patch: Partial<ListingDraft>) => {
    setDraft({ ...draft, ...patch });
    setMessage(null);
  };
  const input = { borderWidth: 1, borderColor: colors.border, borderRadius: 12, padding: spacing.md, color: colors.text, fontSize: 16 } as const;

  const save = async () => {
    const problem = checkDraft(draft);
    if (problem) {
      setMessage(PROBLEMS[problem]);
      return;
    }
    setBusy(true);
    const result = await saveListing(draft);
    setBusy(false);
    if (result.error) {
      setMessage(result.error);
      return;
    }
    await refreshListings();
    router.back();
  };

  return (
    <Screen edges={['bottom']}>
      <Stack.Screen options={{ title: id ? 'Edit offer' : 'New offer' }} />

      <Field label="Name *">
        <TextInput value={draft.title} onChangeText={(title) => set({ title })} placeholder="Riad Dar Anika" placeholderTextColor={colors.textMuted} style={input} accessibilityLabel="Name" />
      </Field>

      <Field label="Category">
        <Row style={{ flexWrap: 'wrap' }}>
          {CATEGORIES.map((c) => (
            <Chip key={c} label={c} selected={draft.category === c} onPress={() => set({ category: c, subtype: SUBTYPES[c][0] ?? null })} />
          ))}
        </Row>
      </Field>

      <Field label="Type">
        <Row style={{ flexWrap: 'wrap' }}>
          {SUBTYPES[draft.category].map((st) => (
            <Chip key={st} label={st.replace('_', ' ')} selected={draft.subtype === st} onPress={() => set({ subtype: st })} />
          ))}
        </Row>
      </Field>

      <Field label="City (empty = all of Morocco)">
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: spacing.sm }}>
          <Chip label="All Morocco" selected={!draft.destination_id} onPress={() => set({ destination_id: null })} />
          {catalog.destinations.map((d) => (
            <Chip key={d.id} label={d.name.en} selected={draft.destination_id === d.id} onPress={() => set({ destination_id: d.id })} />
          ))}
        </ScrollView>
      </Field>

      <Field label="Short label (shown on the card)">
        <TextInput value={draft.subtitle} onChangeText={(subtitle) => set({ subtitle })} placeholder="Rooftop terrace, near Bab Boujloud" placeholderTextColor={colors.textMuted} style={input} accessibilityLabel="Short label" />
      </Field>

      <Field label="Description">
        <TextInput value={draft.description} onChangeText={(description) => set({ description })} multiline placeholderTextColor={colors.textMuted} style={[input, { minHeight: 100, textAlignVertical: 'top' }]} accessibilityLabel="Description" />
      </Field>

      <Field label="Price from (MAD, per night or per person)">
        <TextInput value={draft.price} onChangeText={(price) => set({ price })} keyboardType="number-pad" placeholder="900" placeholderTextColor={colors.textMuted} style={input} accessibilityLabel="Price from" />
      </Field>

      <Field label="Photo address (https://…)">
        <TextInput value={draft.image_url} onChangeText={(image_url) => set({ image_url })} autoCapitalize="none" keyboardType="url" placeholder="https://comemorocco.com/wp-content/uploads/…" placeholderTextColor={colors.textMuted} style={input} accessibilityLabel="Photo address" />
        {/^https:\/\/\S+$/.test(draft.image_url.trim()) ? (
          <Image source={draft.image_url.trim()} style={{ height: 140, borderRadius: 12, backgroundColor: colors.surfaceAlt }} contentFit="cover" />
        ) : null}
      </Field>

      <Field label="Booking link (https://…)">
        <TextInput value={draft.link_url} onChangeText={(link_url) => set({ link_url })} autoCapitalize="none" keyboardType="url" placeholder="https://www.booking.com/hotel/ma/…" placeholderTextColor={colors.textMuted} style={input} accessibilityLabel="Booking link" />
        <Row style={{ justifyContent: 'space-between' }}>
          <T style={{ flex: 1 }}>Partner / affiliate link (earns a commission, tracked and kept private)</T>
          <Switch value={draft.link_is_partner} onValueChange={(link_is_partner) => set({ link_is_partner })} accessibilityLabel="Partner link" />
        </Row>
      </Field>

      <Field label="Partner or owner name">
        <TextInput value={draft.partner_name} onChangeText={(partner_name) => set({ partner_name })} placeholder="Booking.com, or the riad's name" placeholderTextColor={colors.textMuted} style={input} accessibilityLabel="Partner name" />
      </Field>

      <Field label="Status">
        <Row style={{ flexWrap: 'wrap' }}>
          {STATUSES.map((s) => (
            <Chip key={s} label={s} selected={draft.status === s} onPress={() => set({ status: s })} />
          ))}
        </Row>
        <T variant="caption" tone="muted">
          Only published offers appear in the app.
        </T>
      </Field>

      {message ? <T tone="error">{message}</T> : null}
      <Button label={id ? 'Save changes' : 'Add offer'} icon="save-outline" onPress={save} loading={busy} />
    </Screen>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <View style={{ gap: spacing.sm }}>
      <T variant="label">{label}</T>
      {children}
    </View>
  );
}
