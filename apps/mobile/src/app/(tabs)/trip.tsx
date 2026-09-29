/**
 * My Trip (Master Plan §20–21, §34). Guests see the planning entry points
 * and the offline essentials; saving and syncing a trip needs an account.
 */
import { spacing } from '@comemorocco/ui';
import Ionicons from '@expo/vector-icons/Ionicons';
import { router } from 'expo-router';
import { useState } from 'react';
import { Linking, Pressable, View } from 'react-native';

import { Button, Card, EmptyState, Pill, Row, Screen, SectionHeader, T } from '@/components/ui';
import { EMERGENCY_CONTACTS, PHRASES } from '@/data/essentials';
import { useApp } from '@/lib/app-state';
import { useAuth } from '@/lib/auth';

export default function Trip() {
  const { t, colors } = useApp();
  const { userId } = useAuth();
  const [showAllPhrases, setShowAllPhrases] = useState(false);

  return (
    <Screen edges={[]}>
      <EmptyState icon="map-outline" title={t('trip.empty')} body={t('trip.emptyHint')}>
        <Button label={t('trip.askAiToPlan')} icon="sparkles" onPress={() => router.push('/ai')} />
        {userId ? (
          <Button label={t('trip.create')} kind="secondary" icon="add" onPress={() => router.push('/ai')} />
        ) : (
          <Button label={t('common.signIn')} kind="secondary" icon="person-outline" onPress={() => router.push('/sign-in')} />
        )}
        {!userId ? (
          <T variant="caption" tone="muted" style={{ textAlign: 'center' }}>
            {t('trip.signInToSave')}
          </T>
        ) : null}
      </EmptyState>

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
                style={{
                  flexDirection: 'row',
                  alignItems: 'center',
                  gap: 6,
                  backgroundColor: colors.error,
                  paddingHorizontal: 14,
                  paddingVertical: 8,
                  borderRadius: 999,
                }}>
                <Ionicons name="call" size={16} color={colors.surface} />
                <T variant="bodyStrong" style={{ color: colors.surface }}>
                  {c.number}
                </T>
              </Pressable>
            </Row>
            <Row>
              {c.last_verified ? (
                <Pill label={`✓ ${c.last_verified}`} />
              ) : (
                <Pill label={t('trip.unverified')} tone="warning" />
              )}
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
    </Screen>
  );
}
