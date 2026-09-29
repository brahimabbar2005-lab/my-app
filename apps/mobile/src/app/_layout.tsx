import { DarkTheme, DefaultTheme, Stack, ThemeProvider } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { useEffect, useMemo } from 'react';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { configureAnalytics, track } from '@/lib/analytics';
import { AppStateProvider, useApp } from '@/lib/app-state';
import { AuthProvider } from '@/lib/auth';

SplashScreen.preventAutoHideAsync().catch(() => {});

export default function RootLayout() {
  return (
    <SafeAreaProvider>
      <AppStateProvider>
        <AuthProvider>
          <Root />
        </AuthProvider>
      </AppStateProvider>
    </SafeAreaProvider>
  );
}

function Root() {
  const { ready, prefs, scheme, colors, locale, t } = useApp();

  useEffect(() => {
    if (!ready) return;
    configureAnalytics(prefs.anonymousId, { language: locale, ...(prefs.tripStage ? { trip_stage: prefs.tripStage } : {}) });
    SplashScreen.hideAsync().catch(() => {});
  }, [ready, prefs.anonymousId, prefs.tripStage, locale]);

  useEffect(() => {
    if (ready) track('app_opened');
  }, [ready]);

  const navTheme = useMemo(() => {
    const base = scheme === 'dark' ? DarkTheme : DefaultTheme;
    return {
      ...base,
      colors: {
        ...base.colors,
        primary: colors.primary,
        background: colors.background,
        card: colors.surface,
        text: colors.text,
        border: colors.border,
      },
    };
  }, [scheme, colors]);

  if (!ready) return null;

  return (
    <ThemeProvider value={navTheme}>
      <StatusBar style={scheme === 'dark' ? 'light' : 'dark'} />
      <Stack screenOptions={{ headerShown: false, headerTintColor: colors.primary }}>
        <Stack.Screen name="(tabs)" />
        <Stack.Screen name="onboarding" options={{ gestureEnabled: false, animation: 'fade' }} />
        <Stack.Screen name="settings" options={{ headerShown: true, title: t('settings.title'), presentation: 'modal' }} />
        <Stack.Screen name="sign-in" options={{ headerShown: true, title: t('common.signIn'), presentation: 'modal' }} />
        <Stack.Screen name="destinations/[id]" options={{ headerShown: true, title: '' }} />
      </Stack>
    </ThemeProvider>
  );
}
