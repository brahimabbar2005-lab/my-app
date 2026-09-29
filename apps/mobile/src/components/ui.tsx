/**
 * Base UI primitives built on the shared design tokens. Every colour comes
 * from `useApp().colors`, so light/dark mode is automatic; layout uses
 * logical properties (start/end), so Arabic RTL mirrors correctly.
 */
import { MAX_CONTENT_WIDTH, radii, spacing, typography } from '@comemorocco/ui';
import Ionicons from '@expo/vector-icons/Ionicons';
import type { ComponentProps, ReactNode } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  type ScrollViewProps,
  StyleSheet,
  Text,
  type TextProps,
  View,
  type ViewProps,
  type ViewStyle,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useApp } from '@/lib/app-state';

export type IconName = ComponentProps<typeof Ionicons>['name'];

type Variant = keyof typeof typography;
type Tone = 'default' | 'muted' | 'primary' | 'secondary' | 'onPrimary' | 'error' | 'success' | 'warning';

export function T({
  variant = 'body',
  tone = 'default',
  style,
  ...rest
}: TextProps & { variant?: Variant; tone?: Tone }) {
  const { colors, rtl } = useApp();
  const color = {
    default: colors.text,
    muted: colors.textMuted,
    primary: colors.primary,
    secondary: colors.secondary,
    onPrimary: colors.onPrimary,
    error: colors.error,
    success: colors.success,
    warning: colors.warning,
  }[tone];
  return (
    <Text
      {...rest}
      style={[
        typography[variant] as object,
        { color, writingDirection: rtl ? 'rtl' : 'ltr', textAlign: 'auto' },
        style,
      ]}
    />
  );
}

export function Screen({
  children,
  scroll = true,
  edges = ['top'],
  contentStyle,
  ...rest
}: {
  children: ReactNode;
  scroll?: boolean;
  edges?: ('top' | 'bottom')[];
  contentStyle?: ViewStyle;
} & ScrollViewProps) {
  const { colors } = useApp();
  const inner = <View style={[styles.content, contentStyle]}>{children}</View>;
  return (
    <SafeAreaView edges={edges} style={{ flex: 1, backgroundColor: colors.background }}>
      {scroll ? (
        <ScrollView {...rest} contentContainerStyle={{ paddingBottom: spacing.xxxl }} keyboardShouldPersistTaps="handled">
          {inner}
        </ScrollView>
      ) : (
        inner
      )}
    </SafeAreaView>
  );
}

export function Card({ style, children, ...rest }: ViewProps) {
  const { colors } = useApp();
  return (
    <View
      {...rest}
      style={[
        { backgroundColor: colors.surface, borderColor: colors.border, borderWidth: StyleSheet.hairlineWidth },
        styles.card,
        style,
      ]}>
      {children}
    </View>
  );
}

export function SectionHeader({ title, action, onAction }: { title: string; action?: string; onAction?: () => void }) {
  return (
    <View style={styles.sectionHeader}>
      <T variant="heading" accessibilityRole="header" style={{ flex: 1 }}>
        {title}
      </T>
      {action && onAction ? (
        <Pressable onPress={onAction} hitSlop={8} accessibilityRole="button">
          <T variant="caption" tone="secondary">
            {action}
          </T>
        </Pressable>
      ) : null}
    </View>
  );
}

export function Chip({
  label,
  selected,
  onPress,
  icon,
}: {
  label: string;
  selected?: boolean;
  onPress?: () => void;
  icon?: IconName;
}) {
  const { colors } = useApp();
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityState={{ selected: !!selected }}
      style={({ pressed }) => [
        styles.chip,
        {
          backgroundColor: selected ? colors.primary : colors.surface,
          borderColor: selected ? colors.primary : colors.border,
          opacity: pressed ? 0.8 : 1,
        },
      ]}>
      {icon ? <Ionicons name={icon} size={16} color={selected ? colors.onPrimary : colors.text} /> : null}
      <T variant="label" style={{ color: selected ? colors.onPrimary : colors.text }}>
        {label}
      </T>
    </Pressable>
  );
}

export function Button({
  label,
  onPress,
  kind = 'primary',
  icon,
  disabled,
  loading,
}: {
  label: string;
  onPress?: () => void;
  kind?: 'primary' | 'secondary' | 'ghost' | 'danger';
  icon?: IconName;
  disabled?: boolean;
  loading?: boolean;
}) {
  const { colors } = useApp();
  const palette = {
    primary: { bg: colors.primary, fg: colors.onPrimary, border: colors.primary },
    secondary: { bg: colors.surface, fg: colors.secondary, border: colors.border },
    ghost: { bg: 'transparent', fg: colors.secondary, border: 'transparent' },
    danger: { bg: colors.surface, fg: colors.error, border: colors.error },
  }[kind];
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled || loading}
      accessibilityRole="button"
      accessibilityState={{ disabled: !!(disabled || loading) }}
      style={({ pressed }) => [
        styles.button,
        { backgroundColor: palette.bg, borderColor: palette.border, opacity: disabled ? 0.5 : pressed ? 0.85 : 1 },
      ]}>
      {loading ? (
        <ActivityIndicator color={palette.fg} />
      ) : (
        <>
          {icon ? <Ionicons name={icon} size={18} color={palette.fg} /> : null}
          <T variant="bodyStrong" style={{ color: palette.fg }}>
            {label}
          </T>
        </>
      )}
    </Pressable>
  );
}

export function EmptyState({
  icon,
  title,
  body,
  children,
}: {
  icon: IconName;
  title: string;
  body?: string;
  children?: ReactNode;
}) {
  const { colors } = useApp();
  return (
    <Card style={styles.empty}>
      <View style={[styles.emptyIcon, { backgroundColor: colors.surfaceAlt }]}>
        <Ionicons name={icon} size={28} color={colors.primary} />
      </View>
      <T variant="heading" style={{ textAlign: 'center' }}>
        {title}
      </T>
      {body ? (
        <T tone="muted" style={{ textAlign: 'center' }}>
          {body}
        </T>
      ) : null}
      {children ? <View style={{ gap: spacing.sm, alignSelf: 'stretch' }}>{children}</View> : null}
    </Card>
  );
}

export function Row({ style, ...rest }: ViewProps) {
  return <View {...rest} style={[{ flexDirection: 'row', alignItems: 'center', gap: spacing.sm }, style]} />;
}

export function Pill({ label, tone = 'muted' }: { label: string; tone?: 'muted' | 'accent' | 'warning' }) {
  const { colors } = useApp();
  const bg = tone === 'accent' ? colors.accent : colors.surfaceAlt;
  const fg = tone === 'accent' ? colors.onAccent : tone === 'warning' ? colors.warning : colors.textMuted;
  return (
    <View style={[styles.pill, { backgroundColor: bg }]}>
      <T variant="label" style={{ color: fg }}>
        {label}
      </T>
    </View>
  );
}

const styles = StyleSheet.create({
  content: { width: '100%', maxWidth: MAX_CONTENT_WIDTH, alignSelf: 'center', padding: spacing.lg, gap: spacing.xl },
  card: { borderRadius: radii.lg, padding: spacing.lg, gap: spacing.sm },
  sectionHeader: { flexDirection: 'row', alignItems: 'center', marginBottom: -spacing.sm },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radii.pill,
    borderWidth: 1,
  },
  button: {
    minHeight: 48,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
    paddingHorizontal: spacing.lg,
    borderRadius: radii.md,
    borderWidth: 1,
  },
  empty: { alignItems: 'center', paddingVertical: spacing.xxl, gap: spacing.md },
  emptyIcon: { width: 56, height: 56, borderRadius: 28, alignItems: 'center', justifyContent: 'center' },
  pill: { paddingHorizontal: spacing.sm, paddingVertical: 2, borderRadius: radii.pill, alignSelf: 'flex-start' },
});
