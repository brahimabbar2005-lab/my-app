/**
 * My Trip (Master Plan §20–21, §34). Local-first: guests plan on the device;
 * signed-in travellers are synced to their account. Offline essentials stay
 * at the bottom so they are one tap away during the trip.
 */
import { radii, spacing } from '@comemorocco/ui';
import Ionicons from '@expo/vector-icons/Ionicons';
import { router } from 'expo-router';
import { useState } from 'react';
import { Linking, Pressable, Share, StyleSheet, TextInput, View } from 'react-native';

import { Button, Card, Chip, EmptyState, Pill, Row, Screen, SectionHeader, T } from '@/components/ui';
import { EMERGENCY_CONTACTS, PHRASES } from '@/data/essentials';
import { useApp } from '@/lib/app-state';
import { useAuth } from '@/lib/auth';
import { itemsForDay, type TripItem, tripToText } from '@/lib/trip-model';
import { useTrip } from '@/lib/trip-store';

const ITEM_ICON: Record<TripItem['type'], keyof typeof Ionicons.glyphMap> = {
  destination: 'location-outline',
  listing: 'compass-outline',
  activity: 'compass-outline',
  article: 'book-outline',
  note: 'create-outline',
};

export default function TripScreen() {
  const { t } = useApp();
  const { state, createTrip } = useTrip();

  return (
    <Screen edges={[]}>
      {state.trip ? (
        <TripPlanner />
      ) : (
        <EmptyState icon="map-outline" title={t('trip.empty')} body={t('trip.emptyHint')}>
          <Button label={t('trip.create')} icon="add" onPress={() => createTrip({ dayCount: 3 })} />
          <Button label={t('trip.askAiToPlan')} kind="secondary" icon="sparkles" onPress={() => router.push('/ai')} />
        </EmptyState>
      )}
      <SavedPlaces />
      <Essentials />
    </Screen>
  );
}

function SyncNote() {
  const { t } = useApp();
  const { userId } = useAuth();
  const { sync } = useTrip();
  const text =
    sync === 'synced' ? t('trip.synced') : sync === 'syncing' ? t('trip.syncing') : sync === 'error' ? t('trip.syncError') : t('trip.storedOnDevice');
  return (
    <Pressable onPress={userId ? undefined : () => router.push('/sign-in')} disabled={!!userId}>
      <T variant="caption" tone={sync === 'error' ? 'warning' : 'muted'}>
        {sync === 'synced' ? '✓ ' : ''}
        {text}
      </T>
    </Pressable>
  );
}

function Stepper({ label, value, onChange, min, max }: { label: string; value: number; onChange: (n: number) => void; min: number; max: number }) {
  const { colors } = useApp();
  return (
    <View style={{ flex: 1, gap: 4 }}>
      <T variant="label" tone="muted">
        {label}
      </T>
      <Row style={[styles.stepper, { borderColor: colors.border }]}>
        <Pressable onPress={() => onChange(value - 1)} disabled={value <= min} accessibilityLabel={`${label} −`} hitSlop={6}>
          <Ionicons name="remove" size={18} color={value <= min ? colors.border : colors.primary} />
        </Pressable>
        <T variant="bodyStrong" style={{ minWidth: 24, textAlign: 'center' }}>
          {value}
        </T>
        <Pressable onPress={() => onChange(value + 1)} disabled={value >= max} accessibilityLabel={`${label} +`} hitSlop={6}>
          <Ionicons name="add" size={18} color={value >= max ? colors.border : colors.primary} />
        </Pressable>
      </Row>
    </View>
  );
}

function TripPlanner() {
  const { t, colors } = useApp();
  const trip = useTrip();
  const current = trip.state.trip!;
  const [confirmDelete, setConfirmDelete] = useState(false);

  const share = () =>
    Share.share({
      message: tripToText(current, {
        day: (n) => t('trip.day', { n }),
        ideas: t('trip.unscheduled'),
        untitled: t('trip.untitled'),
      }),
    });

  const ideas = itemsForDay(current, null);

  return (
    <View style={{ gap: spacing.lg }}>
      <Card>
        <TextInput
          value={current.title}
          onChangeText={(title) => trip.updateTrip({ title })}
          placeholder={t('trip.untitled')}
          placeholderTextColor={colors.textMuted}
          accessibilityLabel={t('trip.titlePlaceholder')}
          style={[styles.title, { color: colors.text }]}
          maxLength={120}
        />
        <Row style={{ gap: spacing.md }}>
          <Stepper label={t('trip.days')} value={current.dayCount} min={1} max={30} onChange={trip.setDayCount} />
          <Stepper label={t('trip.adults')} value={current.adults} min={0} max={50} onChange={(adults) => trip.updateTrip({ adults })} />
          <Stepper
            label={t('trip.children')}
            value={current.children}
            min={0}
            max={50}
            onChange={(children) => trip.updateTrip({ children })}
          />
        </Row>
        <SyncNote />
      </Card>

      <Row style={{ flexWrap: 'wrap' }}>
        <Chip label={t('trip.askAiToPlan')} icon="sparkles-outline" onPress={() => router.push('/ai')} />
        <Chip label={t('trip.share')} icon="share-outline" onPress={share} />
      </Row>

      <SectionHeader title={t('trip.itinerary')} />
      {Array.from({ length: current.dayCount }, (_, i) => i + 1).map((day) => (
        <DayCard key={day} day={day} />
      ))}

      {ideas.length ? (
        <View style={{ gap: spacing.sm }}>
          <T variant="heading">{t('trip.ideas')}</T>
          {ideas.map((item) => (
            <Card key={item.id}>
              <ItemRow item={item} />
              <Row style={{ flexWrap: 'wrap' }}>
                <T variant="caption" tone="muted">
                  {t('trip.planFor')}
                </T>
                {Array.from({ length: current.dayCount }, (_, i) => i + 1).map((day) => (
                  <Chip key={day} label={t('trip.day', { n: day })} onPress={() => trip.setItemDay(item.id, day)} />
                ))}
              </Row>
            </Card>
          ))}
        </View>
      ) : null}

      <View style={{ gap: spacing.sm }}>
        <T variant="heading">{t('trip.notes')}</T>
        <TextInput
          value={current.notes}
          onChangeText={(notes) => trip.updateTrip({ notes })}
          placeholder={t('trip.notesPlaceholder')}
          placeholderTextColor={colors.textMuted}
          multiline
          accessibilityLabel={t('trip.notes')}
          style={[styles.notes, { color: colors.text, borderColor: colors.border, backgroundColor: colors.surface }]}
        />
      </View>

      {confirmDelete ? (
        <Card style={{ borderColor: colors.error }}>
          <T>{t('trip.deleteTripConfirm')}</T>
          <Row>
            <View style={{ flex: 1 }}>
              <Button label={t('common.cancel')} kind="secondary" onPress={() => setConfirmDelete(false)} />
            </View>
            <View style={{ flex: 1 }}>
              <Button label={t('trip.deleteTrip')} kind="danger" onPress={() => trip.deleteTrip()} />
            </View>
          </Row>
        </Card>
      ) : (
        <Button label={t('trip.deleteTrip')} kind="ghost" icon="trash-outline" onPress={() => setConfirmDelete(true)} />
      )}
    </View>
  );
}

function DayCard({ day }: { day: number }) {
  const { t, colors } = useApp();
  const { state } = useTrip();
  const items = itemsForDay(state.trip!, day);
  return (
    <Card>
      <Row>
        <View style={[styles.dayBadge, { backgroundColor: colors.primary }]}>
          <T variant="label" tone="onPrimary">
            {day}
          </T>
        </View>
        <T variant="bodyStrong">{t('trip.day', { n: day })}</T>
      </Row>
      {items.length ? (
        items.map((item) => <ItemRow key={item.id} item={item} />)
      ) : (
        <T variant="caption" tone="muted">
          {t('trip.emptyDay')}
        </T>
      )}
    </Card>
  );
}

function ItemRow({ item }: { item: TripItem }) {
  const { t, colors } = useApp();
  const { moveItem, removeItem } = useTrip();
  const openable = item.type === 'destination' && item.refId;
  return (
    <Row style={styles.item}>
      <Ionicons name={ITEM_ICON[item.type]} size={18} color={colors.secondary} />
      <Pressable
        style={{ flex: 1 }}
        disabled={!openable}
        onPress={() => openable && router.push({ pathname: '/destinations/[id]', params: { id: item.refId! } })}>
        <T numberOfLines={2}>{item.title}</T>
      </Pressable>
      {item.day !== null ? (
        <>
          <IconButton icon="chevron-up" label={t('trip.moveUp')} onPress={() => moveItem(item.id, -1)} />
          <IconButton icon="chevron-down" label={t('trip.moveDown')} onPress={() => moveItem(item.id, 1)} />
        </>
      ) : null}
      <IconButton icon="close" label={t('trip.remove')} onPress={() => removeItem(item.id)} />
    </Row>
  );
}

function IconButton({ icon, label, onPress }: { icon: keyof typeof Ionicons.glyphMap; label: string; onPress: () => void }) {
  const { colors } = useApp();
  return (
    <Pressable onPress={onPress} accessibilityRole="button" accessibilityLabel={label} hitSlop={8} style={styles.iconButton}>
      <Ionicons name={icon} size={18} color={colors.textMuted} />
    </Pressable>
  );
}

function SavedPlaces() {
  const { t, colors } = useApp();
  const { state, toggleSaved, addItem, hasItem } = useTrip();
  return (
    <View style={{ gap: spacing.md }}>
      <SectionHeader title={t('trip.saved')} />
      {state.saved.length ? (
        <Card>
          {state.saved.map((place, i) => (
            <Row key={`${place.refType}:${place.refId}`} style={[styles.item, i ? { borderTopWidth: 1, borderTopColor: colors.border } : null]}>
              <Ionicons name="heart" size={16} color={colors.primary} />
              <Pressable
                style={{ flex: 1 }}
                disabled={place.refType !== 'destination'}
                onPress={() => router.push({ pathname: '/destinations/[id]', params: { id: place.refId } })}>
                <T numberOfLines={1}>{place.title}</T>
              </Pressable>
              {place.refType === 'destination' || place.refType === 'listing' ? (
                hasItem(place.refType, place.refId) ? (
                  <Ionicons name="checkmark-circle" size={18} color={colors.success} accessibilityLabel={t('trip.inTrip')} />
                ) : (
                  <IconButton
                    icon="add-circle-outline"
                    label={t('trip.addToTrip')}
                    onPress={() => addItem({ type: place.refType as 'destination' | 'listing', refId: place.refId, title: place.title })}
                  />
                )
              ) : null}
              <IconButton icon="close" label={t('trip.remove')} onPress={() => toggleSaved(place)} />
            </Row>
          ))}
        </Card>
      ) : (
        <T variant="caption" tone="muted">
          {t('trip.savedEmpty')}
        </T>
      )}
    </View>
  );
}

function Essentials() {
  const { t, colors } = useApp();
  const [showAllPhrases, setShowAllPhrases] = useState(false);
  return (
    <>
      <View style={{ gap: spacing.md }}>
        <SectionHeader title={t('trip.emergency')} />
        {EMERGENCY_CONTACTS.map((c) => (
          <Card key={c.id}>
            <Row>
              <View style={{ flex: 1, gap: 2 }}>
                <T variant="bodyStrong">{c.label}</T>
                <T variant="caption" tone="muted">
                  {c.scope}
                </T>
              </View>
              <Pressable
                onPress={() => Linking.openURL(`tel:${c.number}`)}
                accessibilityRole="button"
                accessibilityLabel={`${c.label} ${c.number}`}
                style={[styles.call, { backgroundColor: colors.error }]}>
                <Ionicons name="call" size={16} color={colors.surface} />
                <T variant="bodyStrong" style={{ color: colors.surface }}>
                  {c.number}
                </T>
              </Pressable>
            </Row>
            <Row>
              {c.last_verified ? <Pill label={`✓ ${c.last_verified}`} /> : <Pill label={t('trip.unverified')} tone="warning" />}
              <T variant="caption" tone="muted" style={{ flex: 1 }}>
                {c.source}
              </T>
            </Row>
          </Card>
        ))}
      </View>

      <View style={{ gap: spacing.md }}>
        <SectionHeader
          title={t('trip.phrasebook')}
          action={showAllPhrases ? undefined : t('common.seeAll')}
          onAction={() => setShowAllPhrases(true)}
        />
        <Card>
          {(showAllPhrases ? PHRASES : PHRASES.slice(0, 5)).map((p, i) => (
            <Row key={p.en} style={{ paddingVertical: 6, borderTopWidth: i ? 1 : 0, borderTopColor: colors.border }}>
              <T style={{ flex: 1 }}>{p.en}</T>
              <View style={{ alignItems: 'flex-end' }}>
                <T variant="bodyStrong">{p.pronunciation}</T>
                <T variant="caption" tone="muted">
                  {p.darija}
                </T>
              </View>
            </Row>
          ))}
        </Card>
      </View>
    </>
  );
}

const styles = StyleSheet.create({
  title: { fontSize: 22, fontWeight: '700', paddingVertical: 4 },
  stepper: { justifyContent: 'space-between', borderWidth: 1, borderRadius: radii.md, paddingHorizontal: spacing.sm, paddingVertical: 6 },
  dayBadge: { width: 26, height: 26, borderRadius: 13, alignItems: 'center', justifyContent: 'center' },
  item: { paddingVertical: 6, gap: spacing.sm },
  iconButton: { padding: 2 },
  notes: { minHeight: 90, borderWidth: 1, borderRadius: radii.md, padding: spacing.md, fontSize: 16, textAlignVertical: 'top' },
  call: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 14, paddingVertical: 8, borderRadius: 999 },
});
