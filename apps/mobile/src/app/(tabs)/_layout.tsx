import Ionicons from '@expo/vector-icons/Ionicons';
import { Redirect, router } from 'expo-router';
import { Tabs } from 'expo-router/js-tabs';
import type { ComponentProps } from 'react';
import { type ColorValue, Platform, Pressable } from 'react-native';

import { useApp } from '@/lib/app-state';
import { useAuth } from '@/lib/auth';

type IconName = ComponentProps<typeof Ionicons>['name'];

function tabIcon(active: IconName, inactive: IconName) {
  return function TabIcon({ color, focused, size }: { color: ColorValue; focused: boolean; size: number }) {
    return <Ionicons name={focused ? active : inactive} size={size} color={color} />;
  };
}

function ProfileButton() {
  const { colors, t } = useApp();
  const { userId } = useAuth();
  return (
    <Pressable
      onPress={() => router.push('/settings')}
      accessibilityRole="button"
      accessibilityLabel={t('settings.title')}
      hitSlop={10}
      style={{ marginHorizontal: 16 }}>
      <Ionicons name={userId ? 'person-circle' : 'person-circle-outline'} size={30} color={colors.primary} />
    </Pressable>
  );
}

export default function TabsLayout() {
  const { prefs, colors, t } = useApp();
  if (!prefs.onboarded) return <Redirect href="/onboarding" />;

  return (
    <Tabs
      screenOptions={{
        headerShown: true,
        headerRight: () => <ProfileButton />,
        headerStyle: { backgroundColor: colors.background },
        headerShadowVisible: false,
        headerTitleStyle: { color: colors.text, fontWeight: '700' },
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.tabInactive,
        tabBarStyle: {
          backgroundColor: colors.surface,
          borderTopColor: colors.border,
          // Native sizes the bar from safe-area insets; web needs room for the label.
          ...(Platform.OS === 'web' ? { height: 60, paddingBottom: 6 } : null),
        },
        tabBarLabelStyle: { fontWeight: '600', fontSize: 10.5, lineHeight: 14, letterSpacing: -0.1 },
      }}>
      <Tabs.Screen
        name="index"
        options={{ title: t('tabs.explore'), headerTitle: t('common.appName'), tabBarIcon: tabIcon('compass', 'compass-outline') }}
      />
      <Tabs.Screen name="book" options={{ title: t('tabs.book'), tabBarIcon: tabIcon('bed', 'bed-outline') }} />
      <Tabs.Screen
        name="ai"
        options={{ title: t('tabs.ai'), headerTitle: t('ai.title'), tabBarIcon: tabIcon('sparkles', 'sparkles-outline') }}
      />
      <Tabs.Screen
        name="community"
        options={{ title: t('tabs.community'), tabBarIcon: tabIcon('people', 'people-outline') }}
      />
      <Tabs.Screen name="trip" options={{ title: t('tabs.trip'), tabBarIcon: tabIcon('map', 'map-outline') }} />
    </Tabs>
  );
}
