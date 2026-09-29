/**
 * Sign in — optional, never a wall (Master Plan §36–37). Email one-time
 * link works as soon as Supabase is configured; Google and Apple need their
 * native credentials and are enabled in a later build.
 */
import { spacing } from '@comemorocco/ui';
import { router } from 'expo-router';
import { useState } from 'react';
import { TextInput } from 'react-native';

import { Button, Card, Screen, T } from '@/components/ui';
import { useApp } from '@/lib/app-state';
import { useAuth } from '@/lib/auth';

export default function SignIn() {
  const { t, colors } = useApp();
  const { available, signInWithEmail } = useAuth();
  const [email, setEmail] = useState('');
  const [state, setState] = useState<'idle' | 'sending' | 'sent' | 'error'>('idle');
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setState('sending');
    const result = await signInWithEmail(email.trim());
    if (result.error) {
      setError(result.error);
      setState('error');
    } else {
      setState('sent');
    }
  };

  return (
    <Screen edges={['bottom']}>
      <T variant="title">{t('auth.title')}</T>
      <T tone="muted">{t('auth.why')}</T>

      {!available ? (
        <Card>
          <T tone="warning">{t('auth.notConfigured')}</T>
        </Card>
      ) : (
        <Card>
          <TextInput
            value={email}
            onChangeText={setEmail}
            placeholder="you@example.com"
            placeholderTextColor={colors.textMuted}
            autoCapitalize="none"
            autoComplete="email"
            keyboardType="email-address"
            accessibilityLabel="Email"
            style={{
              borderWidth: 1,
              borderColor: colors.border,
              borderRadius: 12,
              padding: spacing.md,
              fontSize: 16,
              color: colors.text,
            }}
          />
          <Button
            label={t('auth.email')}
            icon="mail-outline"
            onPress={submit}
            loading={state === 'sending'}
            disabled={!/^\S+@\S+\.\S+$/.test(email.trim())}
          />
          {state === 'sent' ? <T tone="success">✓ {email}</T> : null}
          {state === 'error' && error ? <T tone="error">{error}</T> : null}
        </Card>
      )}

      <Button label={`${t('auth.google')} · ${t('common.comingSoon')}`} kind="secondary" icon="logo-google" disabled />
      <Button label={`${t('auth.apple')} · ${t('common.comingSoon')}`} kind="secondary" icon="logo-apple" disabled />
      <Button label={t('auth.guest')} kind="ghost" onPress={() => router.back()} />
    </Screen>
  );
}
