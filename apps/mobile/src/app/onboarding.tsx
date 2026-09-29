/**
 * Onboarding (Master Plan §48): welcome → what brings you → optional
 * interests → Explore. No account, no location request, nothing required.
 */
import { LOCALE_NAMES, LOCALES, type MessageKey } from '@comemorocco/i18n';
import type { TripStage } from '@comemorocco/shared';
import { radii, spacing } from '@comemorocco/ui';
import Ionicons from '@expo/vector-icons/Ionicons';
import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { ZelligeStar } from '@/components/brand';
import { Button, Chip, type IconName, Row, Screen, T } from '@/components/ui';
import { track } from '@/lib/analytics';
import { useApp } from '@/lib/app-state';

const STAGES: { id: TripStage; icon: IconName; title: MessageKey; hint: MessageKey }[] = [
  { id: 'dreaming', icon: 'sunny-outline', title: 'onboarding.dreaming', hint: 'onboarding.dreamingHint' },
  { id: 'planning', icon: 'calendar-outline', title: 'onboarding.planning', hint: 'onboarding.planningHint' },
  { id: 'in_morocco', icon: 'location-outline', title: 'onboarding.inMorocco', hint: 'onboarding.inMoroccoHint' },
];

const INTERESTS = ['food', 'culture', 'desert', 'beach', 'hiking', 'shopping', 'relax', 'family'] as const;

export default function Onboarding() {
  const { t, colors, prefs, update, locale } = useApp();
  const [stage, setStage] = useState<TripStage | null>(prefs.tripStage);
  const [interests, setInterests] = useState<string[]>(prefs.interests);

  const finish = (skip = false) => {
    update({ onboarded: true, tripStage: skip ? prefs.tripStage : stage, interests: skip ? prefs.interests : interests });
    track('onboarding_completed', { properties: { stage: stage ?? 'none', interests: interests.length, skipped: skip } });
    router.replace('/');
  };

  return (
    <Screen edges={['top', 'bottom']}>
      <View style={[styles.hero, { backgroundColor: colors.primary }]}>
        <ZelligeStar size={220} color="#FFFFFF" opacity={0.10} style={styles.heroStar} />
        <ZelligeStar size={60} color={colors.accent} style={styles.heroStarSmall} />
        <T variant="display" tone="onPrimary">
          {t('onboarding.welcome')}
        </T>
        <T tone="onPrimary">{t('onboarding.subtitle')}</T>
      </View>

      <Row style={{ flexWrap: 'wrap' }}>
        {LOCALES.map((code) => (
          <Chip key={code} label={LOCALE_NAMES[code]} selected={code === locale} onPress={() => update({ locale: code })} />
        ))}
      </Row>

      <View style={{ gap: spacing.md }}>
        <T variant="title" accessibilityRole="header">
          {t('onboarding.question')}
        </T>
        {STAGES.map((s) => {
          const selected = stage === s.id;
          return (
            <Pressable
              key={s.id}
              onPress={() => setStage(s.id)}
              accessibilityRole="radio"
              accessibilityState={{ selected }}
              style={[
                styles.stage,
                { backgroundColor: colors.surface, borderColor: selected ? colors.primary : colors.border },
              ]}>
              <View style={[styles.stageIcon, { backgroundColor: selected ? colors.primary : colors.surfaceAlt }]}>
                <Ionicons name={s.icon} size={22} color={selected ? colors.onPrimary : colors.primary} />
              </View>
              <View style={{ flex: 1 }}>
                <T variant="bodyStrong">{t(s.title)}</T>
                <T variant="caption" tone="muted">
                  {t(s.hint)}
                </T>
              </View>
              <Ionicons
                name={selected ? 'radio-button-on' : 'radio-button-off'}
                size={22}
                color={selected ? colors.primary : colors.textMuted}
              />
            </Pressable>
          );
        })}
      </View>

      <View style={{ gap: spacing.md }}>
        <T variant="heading">{t('onboarding.interests')}</T>
        <Row style={{ flexWrap: 'wrap' }}>
          {INTERESTS.map((id) => (
            <Chip
              key={id}
              label={t(`interests.${id}`)}
              selected={interests.includes(id)}
              onPress={() => setInterests((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]))}
            />
          ))}
        </Row>
      </View>

      <View style={{ gap: spacing.sm }}>
        <Button label={t('onboarding.start')} icon="arrow-forward" onPress={() => finish(false)} disabled={!stage} />
        <Button label={t('onboarding.skip')} kind="ghost" onPress={() => finish(true)} />
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  hero: { borderRadius: radii.xl, padding: spacing.xl, paddingTop: spacing.xxxl * 1.5, gap: spacing.sm, overflow: 'hidden' },
  heroStar: { position: 'absolute', top: -60, end: -50 },
  heroStarSmall: { position: 'absolute', top: spacing.xl, start: spacing.xl },
  stage: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    padding: spacing.lg,
    borderRadius: radii.lg,
    borderWidth: 2,
  },
  stageIcon: { width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center' },
});
