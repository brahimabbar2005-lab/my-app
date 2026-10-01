/**
 * Profile & settings (Master Plan §14, §19, §56). Account deletion is
 * available in the app (Apple 5.1.1(v)) and on the web at
 * comemorocco.com/account-delete (Google Play). Guests can clear the data
 * kept on the device.
 */
import { LOCALE_NAMES, LOCALES } from '@comemorocco/i18n';
import { spacing } from '@comemorocco/ui';
import Constants from 'expo-constants';
import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { Pressable, Share, View } from 'react-native';

import { Button, Card, Chip, Row, Screen, SectionHeader, T } from '@/components/ui';
import { track } from '@/lib/analytics';
import { type ThemePreference, useApp } from '@/lib/app-state';
import { useAuth } from '@/lib/auth';
import { isAdmin } from '@/lib/community';
import { config } from '@/lib/config';
import { openArticle } from '@/lib/links';
import { removeKeys } from '@/lib/storage';
import { supabase } from '@/lib/supabase';

export default function Settings() {
  const { t, locale, prefs, update, rtlRestartNeeded, colors } = useApp();
  const { session, signOut, deleteAccount } = useAuth();
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [admin, setAdmin] = useState(false);

  // The moderation entry appears only for accounts in admin_users.
  useEffect(() => {
    let alive = true;
    if (session) isAdmin().then((yes) => alive && setAdmin(yes));
    return () => {
      alive = false;
    };
  }, [session]);

  const themes: ThemePreference[] = ['system', 'light', 'dark'];

  const exportData = async () => {
    if (!supabase || !session) {
      setMessage(t('trip.signInToSave'));
      return;
    }
    setBusy(true);
    const { data, error } = await supabase.rpc('export_my_data');
    setBusy(false);
    if (error) return setMessage(error.message);
    await Share.share({ message: JSON.stringify(data, null, 2), title: 'ComeMorocco data export' });
  };

  const deleteContent = async () => {
    if (!supabase || !session) return;
    setBusy(true);
    const { error } = await supabase.rpc('delete_my_content');
    setBusy(false);
    setMessage(error ? error.message : '✓');
  };

  const confirmDeletion = async () => {
    setBusy(true);
    if (session) {
      const result = await deleteAccount();
      if (result.error) {
        setBusy(false);
        return setMessage(result.error);
      }
    }
    track('account_deleted', { properties: { signed_in: !!session } });
    await removeKeys(['prefs']);
    update({ onboarded: false, tripStage: null, interests: [] });
    setBusy(false);
    setConfirmDelete(false);
    setMessage(t('settings.deleteAccountDone'));
    router.replace('/onboarding');
  };

  return (
    <Screen edges={['bottom']}>
      <Card>
        {session ? (
          <>
            <T variant="bodyStrong">{session.user.email}</T>
            {admin ? (
              <Button label="Moderation queue" kind="secondary" icon="shield-checkmark-outline" onPress={() => router.push('/admin')} />
            ) : null}
            <Button label={t('common.signOut')} kind="secondary" icon="log-out-outline" onPress={signOut} />
          </>
        ) : (
          <>
            <T tone="muted">{t('auth.why')}</T>
            <Button label={t('common.signIn')} icon="person-outline" onPress={() => router.push('/sign-in')} />
          </>
        )}
      </Card>

      <View style={{ gap: spacing.md }}>
        <SectionHeader title={t('settings.language')} />
        <Row style={{ flexWrap: 'wrap' }}>
          {LOCALES.map((code) => (
            <Chip key={code} label={LOCALE_NAMES[code]} selected={code === locale} onPress={() => update({ locale: code })} />
          ))}
        </Row>
        {rtlRestartNeeded ? (
          <T variant="caption" tone="warning">
            Restart the app to apply the new layout direction.
          </T>
        ) : null}
      </View>

      <View style={{ gap: spacing.md }}>
        <SectionHeader title={t('settings.appearance')} />
        <Row style={{ flexWrap: 'wrap' }}>
          {themes.map((theme) => (
            <Chip key={theme} label={t(`settings.${theme}`)} selected={prefs.theme === theme} onPress={() => update({ theme })} />
          ))}
        </Row>
      </View>

      <View style={{ gap: spacing.md }}>
        <SectionHeader title={t('settings.privacy')} />
        <Card>
          <Button label={t('settings.downloadData')} kind="secondary" icon="download-outline" onPress={exportData} disabled={busy} />
          {session ? (
            <Button label={t('settings.deleteContent')} kind="secondary" icon="trash-outline" onPress={deleteContent} disabled={busy} />
          ) : null}
          {confirmDelete ? (
            <View style={{ gap: spacing.sm, borderColor: colors.error, borderWidth: 1, borderRadius: 12, padding: spacing.md }}>
              <T>{t('settings.deleteAccountConfirm')}</T>
              <Row>
                <View style={{ flex: 1 }}>
                  <Button label={t('common.cancel')} kind="secondary" onPress={() => setConfirmDelete(false)} />
                </View>
                <View style={{ flex: 1 }}>
                  <Button label={t('settings.deleteAccount')} kind="danger" onPress={confirmDeletion} loading={busy} />
                </View>
              </Row>
            </View>
          ) : (
            <Button label={t('settings.deleteAccount')} kind="danger" icon="warning-outline" onPress={() => setConfirmDelete(true)} />
          )}
          <Pressable onPress={() => openArticle(config.accountDeletionUrl, 'settings')} accessibilityRole="link">
            <T variant="caption" tone="secondary">
              {config.accountDeletionUrl.replace('https://', '')}
            </T>
          </Pressable>
          {message ? (
            <T variant="caption" tone="muted">
              {message}
            </T>
          ) : null}
        </Card>
      </View>

      <Card>
        {[
          { label: t('settings.privacyPolicy'), url: config.privacyUrl },
          { label: t('settings.terms'), url: config.termsUrl },
          { label: t('settings.affiliateDisclosure'), url: `${config.siteUrl}/affiliate-disclosure/` },
          { label: t('community.guidelines'), url: `${config.siteUrl}/community-guidelines/` },
          { label: t('settings.support'), url: config.supportUrl },
        ].map((item) => (
          <Pressable key={item.url} onPress={() => openArticle(item.url, 'settings')} accessibilityRole="link" style={{ paddingVertical: 6 }}>
            <T tone="secondary">{item.label}</T>
          </Pressable>
        ))}
        <T variant="caption" tone="muted">
          {t('settings.version')} {Constants.expoConfig?.version ?? '0.1.0'}
        </T>
      </Card>
    </Screen>
  );
}
