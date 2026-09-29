/**
 * "Add to My Trip" and "Save" (heart) controls, usable on any card.
 * Adding works for guests too — the trip lives on the device (trip-store).
 */
import { radii, spacing } from '@comemorocco/ui';
import Ionicons from '@expo/vector-icons/Ionicons';
import { Pressable, StyleSheet } from 'react-native';

import { useApp } from '@/lib/app-state';
import type { NewItem, SavedRefType } from '@/lib/trip-model';
import { useTrip } from '@/lib/trip-store';

import { T } from './ui';

export function AddToTripButton({ item, compact }: { item: NewItem & { refId: string }; compact?: boolean }) {
  const { t, colors } = useApp();
  const { hasItem, addItem } = useTrip();
  const added = hasItem(item.type, item.refId);
  return (
    <Pressable
      onPress={() => addItem(item)}
      disabled={added}
      accessibilityRole="button"
      accessibilityState={{ disabled: added }}
      accessibilityLabel={added ? t('trip.inTrip') : t('trip.addToTrip')}
      hitSlop={6}
      style={({ pressed }) => [
        styles.pill,
        {
          borderColor: added ? colors.success : colors.secondary,
          backgroundColor: colors.surface,
          opacity: pressed ? 0.8 : 1,
        },
      ]}>
      <Ionicons name={added ? 'checkmark-circle' : 'add-circle-outline'} size={16} color={added ? colors.success : colors.secondary} />
      {compact ? null : (
        <T variant="label" style={{ color: added ? colors.success : colors.secondary }}>
          {added ? t('trip.inTrip') : t('trip.addToTrip')}
        </T>
      )}
    </Pressable>
  );
}

export function SaveButton({ refType, refId, title, size = 22, onDark }: {
  refType: SavedRefType;
  refId: string;
  title: string;
  size?: number;
  onDark?: boolean;
}) {
  const { t, colors } = useApp();
  const { isSaved, toggleSaved } = useTrip();
  const saved = isSaved(refType, refId);
  const idle = onDark ? '#FFFFFF' : colors.textMuted;
  return (
    <Pressable
      onPress={() => toggleSaved({ refType, refId, title })}
      accessibilityRole="button"
      accessibilityState={{ selected: saved }}
      accessibilityLabel={saved ? t('trip.savedDone') : t('trip.save')}
      hitSlop={10}>
      <Ionicons name={saved ? 'heart' : 'heart-outline'} size={size} color={saved ? colors.primary : idle} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  pill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    paddingHorizontal: spacing.sm,
    paddingVertical: 6,
    borderRadius: radii.pill,
    borderWidth: 1,
    alignSelf: 'flex-start',
  },
});
