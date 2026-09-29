/**
 * Community (Master Plan §28–29). Posting requires an account, and the
 * report / block / moderation tables exist before any post can be written.
 * No sample posts are shown: invented traveller experiences would be
 * fabricated reviews.
 */
import { spacing } from '@comemorocco/ui';
import { router } from 'expo-router';
import { View } from 'react-native';

import { Button, Card, EmptyState, Row, Screen, T } from '@/components/ui';
import { useApp } from '@/lib/app-state';
import { useAuth } from '@/lib/auth';
import { openArticle } from '@/lib/links';

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
  return (
    <Screen edges={[]}>
      <View style={{ gap: spacing.xs }}>
        <T variant="title">{t('community.title')}</T>
        <T tone="muted">{t('community.subtitle')}</T>
      </View>

      <EmptyState icon="people-outline" title={t('community.empty')}>
        {userId ? (
          <Button label={t('community.ask')} icon="create-outline" disabled />
        ) : (
          <>
            <Button label={t('common.signIn')} icon="person-outline" onPress={() => router.push('/sign-in')} />
            <T variant="caption" tone="muted" style={{ textAlign: 'center' }}>
              {t('community.signInToPost')}
            </T>
          </>
        )}
      </EmptyState>

      <Card>
        <T variant="heading">{t('community.guidelines')}</T>
        {GUIDELINES.map((g) => (
          <Row key={g} style={{ alignItems: 'flex-start' }}>
            <T>•</T>
            <T style={{ flex: 1 }}>{g}</T>
          </Row>
        ))}
        <Button
          label={t('community.guidelines')}
          kind="ghost"
          icon="open-outline"
          onPress={() => openArticle('https://comemorocco.com/community-guidelines/', 'community')}
        />
      </Card>
    </Screen>
  );
}
