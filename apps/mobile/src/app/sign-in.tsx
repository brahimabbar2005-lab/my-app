/**
 * Sign in — optional, never a wall (Master Plan §36–37). The email carries a
 * one-time link and a code; the code works everywhere, including where no
 * deep link is set up. Google and Apple need their native credentials and
 * are enabled in a later build.
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
  const { available, session, signInWithEmail, verifyEmailCode } = useAuth();
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const inputStyle = {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    padding: spacing.md,
    fontSize: 16,
    color: colors.text,
  };

  const submit = async () => {
    setBusy(true);
    setError(null);
    const result = await signInWithEmail(email.trim());
    setBusy(false);
    if (result.error) setError(result.error);
    else setSent(true);
  };

  const verify = async () => {
    setBusy(true);
    setError(null);
    const result = await verifyEmailCode(email.trim(), code.trim());
    setBusy(false);
    if (result.error) setError(result.error);
    else if (router.canGoBack()) router.back();
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
          {session ? <T tone="success">✓ {t('auth.signedIn')}</T> : null}
          <TextInput
            value={email}
            onChangeText={(value) => {
              setEmail(value);
              setSent(false);
            }}
            placeholder="you@example.com"
            placeholderTextColor={colors.textMuted}
            autoCapitalize="none"
            autoComplete="email"
            keyboardType="email-address"
            accessibilityLabel="Email"
            style={inputStyle}
          />
          <Button
            label={t('auth.email')}
            icon="mail-outline"
            kind={sent ? 'secondary' : 'primary'}
            onPress={submit}
            loading={busy && !sent}
            disabled={!/^\S+@\S+\.\S+$/.test(email.trim())}
          />
          {sent ? (
            <>
              <T tone="muted">{t('auth.codeSent', { email: email.trim() })}</T>
              <TextInput
                value={code}
                onChangeText={(value) => setCode(value.replace(/\D/g, ''))}
                placeholder="123456"
                placeholderTextColor={colors.textMuted}
                autoComplete="one-time-code"
                textContentType="oneTimeCode"
                keyboardType="number-pad"
                maxLength={10}
                accessibilityLabel={t('auth.codeLabel')}
                style={[inputStyle, { letterSpacing: 4, fontSize: 20 }]}
              />
              <Button
                label={t('auth.verify')}
                icon="checkmark-circle-outline"
                onPress={verify}
                loading={busy}
                disabled={code.length < 6}
              />
            </>
          ) : null}
          {error ? <T tone="error">{error}</T> : null}
        </Card>
      )}

      <Button label={`${t('auth.google')} · ${t('common.comingSoon')}`} kind="secondary" icon="logo-google" disabled />
      <Button label={`${t('auth.apple')} · ${t('common.comingSoon')}`} kind="secondary" icon="logo-apple" disabled />
      <Button label={t('auth.guest')} kind="ghost" onPress={() => router.back()} />
    </Screen>
  );
}
