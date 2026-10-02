/**
 * ComeMorocco AI (Master Plan §10–12, §40–41).
 *
 * Streams from the AI service; resource cards open the canonical
 * comemorocco.com page with app attribution; partner cards always carry
 * their disclosure and open through the /go click tracker. The assistant is
 * labelled as AI — warm, but never presented as a human.
 */
import {
  type AffiliateCard,
  type AIAction,
  type ChatStreamEvent,
  type Photo,
  getStarters,
  type ResourceCard,
  sendFeedback,
  streamChat,
} from '@comemorocco/shared';
import { radii, spacing } from '@comemorocco/ui';
import Ionicons from '@expo/vector-icons/Ionicons';
import { router, useLocalSearchParams } from 'expo-router';
import { useBottomTabBarHeight } from 'expo-router/build/react-navigation/bottom-tabs';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  Keyboard,
  Platform,
  Pressable,
  StyleSheet,
  TextInput,
  View,
} from 'react-native';

import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { ZelligeStar } from '@/components/brand';
import { PhotoStrip } from '@/components/photos';
import { SimpleMarkdown } from '@/components/markdown';
import { Card, Chip, Row, T } from '@/components/ui';
import { catalog, destinationName, getDestination } from '@/data/catalog';
import { aiClient } from '@/lib/ai';
import { track } from '@/lib/analytics';
import { useApp } from '@/lib/app-state';
import { useAuth } from '@/lib/auth';
import { isActionDone, runAction } from '@/lib/ai-actions';
import { ACTIVITY_TERMS, type LinkTerm } from '@/lib/autolink';
import { parseItinerary } from '@/lib/itinerary';
import { openArticle, openPartner } from '@/lib/links';
import { tripContext } from '@/lib/trip-model';
import { useTrip } from '@/lib/trip-store';

interface Turn {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  resources?: ResourceCard[];
  affiliates?: AffiliateCard[];
  notices?: string[];
  actions?: AIAction[];
  photos?: Photo[];
  messageId?: string;
  pending?: boolean;
  failed?: boolean;
  feedback?: boolean;
}

const LOCAL_STARTERS = [
  'Marrakech or Fes for a first trip?',
  'I have 10 days and want Marrakech and the desert. What would you add?',
  "What's Morocco like in February?",
  'Train, bus or private driver between cities?',
];

export default function AiScreen() {
  const { t, colors, locale, prefs } = useApp();
  const { userId } = useAuth();
  const trip = useTrip();
  // The latest trip, read when a message is sent (not a render dependency).
  const tripRef = useRef(trip.state.trip);
  useEffect(() => {
    tripRef.current = trip.state.trip;
  }, [trip.state.trip]);
  const params = useLocalSearchParams<{ q?: string }>();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [starters, setStarters] = useState<string[]>([]);
  const conversationId = useRef<string | null>(null);
  const abort = useRef<AbortController | null>(null);
  const list = useRef<FlatList<Turn>>(null);
  const keyboardLift = useKeyboardLift();
  const handledQuery = useRef<string | null>(null);

  useEffect(() => {
    getStarters(aiClient, locale).then((s) => setStarters(s.length ? s.slice(0, 4) : LOCAL_STARTERS));
  }, [locale]);

  const patchLast = useCallback((patch: (turn: Turn) => Turn) => {
    setTurns((cur) => {
      const last = cur[cur.length - 1];
      return last ? [...cur.slice(0, -1), patch(last)] : cur;
    });
  }, []);

  const send = useCallback(
    async (text: string) => {
      const message = text.trim();
      if (!message || busy) return;
      setInput('');
      setBusy(true);
      if (!turns.length) track('ai_started');
      track('ai_message_sent', { properties: { length: message.length, signed_in: !!userId } });
      const now = Date.now();
      setTurns((cur) => [
        ...cur,
        { id: `u${now}`, role: 'user', text: message },
        { id: `a${now}`, role: 'assistant', text: '', pending: true },
      ]);
      const controller = new AbortController();
      abort.current = controller;

      const onEvent = (event: ChatStreamEvent) => {
        switch (event.type) {
          case 'meta':
            conversationId.current = event.data.conversation_id;
            patchLast((turn) => ({
              ...turn,
              resources: event.data.resources,
              affiliates: event.data.affiliates,
              notices: event.data.notices,
              actions: event.data.actions,
              photos: event.data.photos,
            }));
            break;
          case 'delta':
            patchLast((turn) => ({ ...turn, text: turn.text + event.data.text }));
            break;
          case 'done':
            conversationId.current = event.data.conversation_id;
            patchLast((turn) => ({ ...turn, pending: false, messageId: event.data.message_id }));
            break;
          case 'error':
            patchLast((turn) => ({
              ...turn,
              pending: false,
              failed: true,
              // Development builds show where the request went and why it failed.
              text: turn.text || (__DEV__ && event.data.detail ? `${event.data.answer}\n\n[dev] ${event.data.detail}` : event.data.answer),
            }));
            break;
        }
      };

      try {
        await streamChat(
          aiClient,
          {
            message,
            session_id: prefs.anonymousId,
            conversation_id: conversationId.current,
            locale,
            trip_context: tripContext(tripRef.current),
          },
          onEvent,
          controller.signal,
        );
      } catch {
        patchLast((turn) => ({ ...turn, pending: false }));
      } finally {
        patchLast((turn) => (turn.pending ? { ...turn, pending: false } : turn));
        setBusy(false);
        abort.current = null;
      }
    },
    [busy, turns.length, userId, prefs.anonymousId, locale, patchLast],
  );

  // Arriving from Explore search with a question.
  useEffect(() => {
    if (params.q && handledQuery.current !== params.q) {
      handledQuery.current = params.q;
      send(params.q);
    }
  }, [params.q, send]);

  const newChat = () => {
    abort.current?.abort();
    conversationId.current = null;
    setTurns([]);
    setBusy(false);
  };

  const rate = async (turn: Turn, helpful: boolean) => {
    if (!turn.messageId || turn.feedback !== undefined) return;
    setTurns((cur) => cur.map((x) => (x.id === turn.id ? { ...x, feedback: helpful } : x)));
    await sendFeedback(aiClient, { message_id: turn.messageId, helpful });
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.background, paddingBottom: keyboardLift }}>
      <FlatList
        ref={list}
        data={turns}
        keyExtractor={(turn) => turn.id}
        onContentSizeChange={() => list.current?.scrollToEnd({ animated: true })}
        contentContainerStyle={styles.listContent}
        ListHeaderComponent={
          turns.length ? (
            <Row style={{ justifyContent: 'flex-end' }}>
              <Chip label={t('ai.newChat')} icon="add" onPress={newChat} />
            </Row>
          ) : (
            <Welcome starters={starters} onPick={send} signedIn={!!userId} />
          )
        }
        renderItem={({ item }) =>
          item.role === 'user' ? (
            <View style={[styles.userBubble, { backgroundColor: colors.secondary }]}>
              <T style={{ color: colors.onSecondary }}>{item.text}</T>
            </View>
          ) : (
            <AssistantTurn turn={item} onRate={(helpful) => rate(item, helpful)} />
          )
        }
      />
      <View style={[styles.composer, { backgroundColor: colors.surface, borderTopColor: colors.border }]}>
        <TextInput
          value={input}
          onChangeText={setInput}
          placeholder={t('ai.placeholder')}
          placeholderTextColor={colors.textMuted}
          style={[styles.input, { color: colors.text, backgroundColor: colors.background, borderColor: colors.border }]}
          multiline
          maxLength={2000}
          onSubmitEditing={() => send(input)}
          blurOnSubmit
          accessibilityLabel={t('ai.placeholder')}
        />
        <Pressable
          onPress={() => send(input)}
          disabled={busy || !input.trim()}
          accessibilityRole="button"
          accessibilityLabel={t('ai.send')}
          style={[styles.send, { backgroundColor: colors.primary, opacity: busy || !input.trim() ? 0.5 : 1 }]}>
          {busy ? <ActivityIndicator color={colors.onPrimary} /> : <Ionicons name="arrow-up" size={22} color={colors.onPrimary} />}
        </Pressable>
      </View>
    </View>
  );
}

function Welcome({ starters, onPick, signedIn }: { starters: string[]; onPick: (q: string) => void; signedIn: boolean }) {
  const { t, colors } = useApp();
  return (
    <View style={{ gap: spacing.lg }}>
      <View style={[styles.welcome, { backgroundColor: colors.secondary }]}>
        <ZelligeStar size={160} color="#FFFFFF" opacity={0.10} style={{ position: 'absolute', top: -40, end: -30 }} />
        <Ionicons name="sparkles" size={28} color={colors.onSecondary} />
        <T variant="title" style={{ color: colors.onSecondary }}>
          {t('ai.title')}
        </T>
        <T style={{ color: colors.onSecondary }}>{t('ai.subtitle')}</T>
      </View>
      <T variant="heading">{t('ai.starters')}</T>
      {starters.map((s) => (
        <Pressable key={s} onPress={() => onPick(s)} accessibilityRole="button">
          <Card>
            <Row>
              <Ionicons name="chatbubble-ellipses-outline" size={18} color={colors.secondary} />
              <T style={{ flex: 1 }}>{s}</T>
            </Row>
          </Card>
        </Pressable>
      ))}
      <T variant="caption" tone="muted">
        {t('ai.disclaimer')}
      </T>
      {!signedIn ? (
        <Pressable onPress={() => router.push('/sign-in')} accessibilityRole="link">
          <T variant="caption" tone="secondary">
            {t('ai.signInForMore')}
          </T>
        </Pressable>
      ) : null}
    </View>
  );
}

function AssistantTurn({ turn, onRate }: { turn: Turn; onRate: (helpful: boolean) => void }) {
  const { t, colors, prefs } = useApp();
  return (
    <View style={{ gap: spacing.sm }}>
      <Row>
        <ZelligeStar size={14} color={colors.primary} />
        <T variant="label" tone="muted">
          {t('ai.title')}
        </T>
      </Row>
      {turn.photos?.length ? <PhotoStrip photos={turn.photos} /> : null}
      <Card style={turn.failed ? { borderColor: colors.warning } : undefined}>
        {turn.text ? (
          <SimpleMarkdown text={turn.text} linkTerms={LINK_TERMS} onLink={(url) => openArticle(url, 'ai')} />
        ) : (
          <Row>
            <ActivityIndicator color={colors.primary} />
            <T tone="muted">{t('ai.thinking')}</T>
          </Row>
        )}
        {turn.notices?.map((notice) => (
          <Row key={notice} style={{ alignItems: 'flex-start' }}>
            <Ionicons name="information-circle-outline" size={16} color={colors.warning} />
            <T variant="caption" tone="warning" style={{ flex: 1 }}>
              {notice}
            </T>
          </Row>
        ))}
      </Card>

      {!turn.pending && !turn.failed ? <SavePlanButton text={turn.text} /> : null}

      {turn.resources?.length ? (
        <View style={{ gap: spacing.sm }}>
          <T variant="label" tone="muted">
            {t('ai.sources')}
          </T>
          {turn.resources.map((r) => (
            <Pressable
              key={r.content_id}
              accessibilityRole="link"
              onPress={() => {
                track('ai_recommendation_clicked', { properties: { kind: 'article', id: r.content_id } });
                openArticle(r.url, 'ai');
              }}>
              <Card style={{ borderColor: colors.secondary }}>
                <Row>
                  <Ionicons name="book-outline" size={18} color={colors.secondary} />
                  <T variant="bodyStrong" style={{ flex: 1 }}>
                    {r.title}
                  </T>
                  <Ionicons name="open-outline" size={16} color={colors.textMuted} />
                </Row>
                <ActionButton action={turn.actions?.find((a) => a.id === `add_to_trip:article:${r.content_id}`)} />
              </Card>
            </Pressable>
          ))}
        </View>
      ) : null}

      {turn.affiliates?.length ? (
        <View style={{ gap: spacing.sm }}>
          <T variant="label" tone="muted">
            {t('ai.partners')}
          </T>
          {turn.affiliates.map((a) => (
            <Pressable
              key={a.affiliate_id}
              accessibilityRole="link"
              onPress={() => {
                track('ai_recommendation_clicked', { listing_id: a.affiliate_id, properties: { kind: 'affiliate' } });
                openPartner(a.affiliate_id, 'ai', prefs.anonymousId);
              }}>
              <Card>
                <Row style={{ alignItems: 'flex-start' }}>
                  <Ionicons name="pricetag-outline" size={18} color={colors.primary} />
                  <View style={{ flex: 1, gap: 2 }}>
                    <T variant="bodyStrong">{a.label}</T>
                    <T variant="caption" tone="muted">
                      {a.category}
                    </T>
                  </View>
                  <Ionicons name="open-outline" size={16} color={colors.textMuted} />
                </Row>
                <T variant="caption" tone="muted">
                  {a.disclosure}
                </T>
                <ActionButton action={turn.actions?.find((x) => x.id === `add_to_trip:listing:${a.affiliate_id}`)} />
              </Card>
            </Pressable>
          ))}
        </View>
      ) : null}

      {turn.actions?.some((a) => a.tool === 'save_place') ? (
        <Row style={{ flexWrap: 'wrap' }}>
          {turn.actions
            .filter((a) => a.tool === 'save_place')
            .map((a) => (
              <ActionButton key={a.id} action={a} />
            ))}
        </Row>
      ) : null}

      {turn.messageId ? (
        <Row>
          <Pressable onPress={() => onRate(true)} accessibilityLabel={t('ai.helpful')} hitSlop={8}>
            <Ionicons name={turn.feedback === true ? 'thumbs-up' : 'thumbs-up-outline'} size={18} color={colors.textMuted} />
          </Pressable>
          <Pressable onPress={() => onRate(false)} accessibilityLabel={t('ai.notHelpful')} hitSlop={8}>
            <Ionicons name={turn.feedback === false ? 'thumbs-down' : 'thumbs-down-outline'} size={18} color={colors.textMuted} />
          </Pressable>
        </Row>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  listContent: { padding: spacing.lg, gap: spacing.lg, maxWidth: 720, width: '100%', alignSelf: 'center' },
  welcome: { borderRadius: radii.xl, padding: spacing.xl, gap: spacing.sm, overflow: 'hidden' },
  userBubble: { alignSelf: 'flex-end', maxWidth: '85%', padding: spacing.md, borderRadius: radii.lg, borderBottomEndRadius: 4 },
  composer: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: spacing.sm,
    padding: spacing.md,
    borderTopWidth: StyleSheet.hairlineWidth,
  },
  input: {
    flex: 1,
    minHeight: 44,
    maxHeight: 140,
    borderRadius: radii.lg,
    borderWidth: 1,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    fontSize: 16,
  },
  action: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    paddingHorizontal: spacing.sm,
    paddingVertical: 6,
    borderRadius: radii.pill,
    borderWidth: 1,
    alignSelf: 'flex-start',
  },
  send: { width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center' },
});

/** A proposed action as a button; runs only on tap, after validation. */
function ActionButton({ action }: { action: AIAction | undefined }) {
  const { t, colors } = useApp();
  const { userId } = useAuth();
  const trip = useTrip();
  if (!action) return null;
  const done = isActionDone(action, trip);
  const isSave = action.tool === 'save_place';
  const label = isSave ? (done ? `${action.label} ✓` : `${t('trip.save')} ${action.label}`) : done ? t('trip.inTrip') : t('trip.addToTrip');
  return (
    <Pressable
      onPress={() => {
        if (runAction(action, trip, { signedIn: !!userId }) === 'done') {
          track('ai_recommendation_clicked', { properties: { kind: 'action', id: action.id } });
        }
      }}
      disabled={done}
      accessibilityRole="button"
      accessibilityState={{ disabled: done }}
      hitSlop={6}
      style={({ pressed }) => [
        styles.action,
        { borderColor: done ? colors.success : colors.secondary, backgroundColor: colors.surface, opacity: pressed ? 0.8 : 1 },
      ]}>
      <Ionicons
        name={done ? 'checkmark-circle' : isSave ? 'heart-outline' : 'add-circle-outline'}
        size={16}
        color={done ? colors.success : colors.secondary}
      />
      <T variant="label" style={{ color: done ? colors.success : colors.secondary }}>
        {label}
      </T>
    </Pressable>
  );
}

/**
 * How much to lift the composer while the keyboard is up. The tab bar stays
 * in place under the keyboard, so the keyboard covers (keyboard height − tab
 * bar height) of this view. Android reports the keyboard height without the
 * navigation bar below it (edge-to-edge), so that bar is added back there.
 * No screen coordinates: they differ between Android versions and modes.
 */
function useKeyboardLift(): number {
  const [keyboardHeight, setKeyboardHeight] = useState(0);
  const tabBarHeight = useBottomTabBarHeight();
  const insets = useSafeAreaInsets();
  useEffect(() => {
    const showEvent = Platform.OS === 'ios' ? 'keyboardWillShow' : 'keyboardDidShow';
    const hideEvent = Platform.OS === 'ios' ? 'keyboardWillHide' : 'keyboardDidHide';
    const show = Keyboard.addListener(showEvent, (e) => setKeyboardHeight(e.endCoordinates.height));
    const hide = Keyboard.addListener(hideEvent, () => setKeyboardHeight(0));
    return () => {
      show.remove();
      hide.remove();
    };
  }, []);
  if (!keyboardHeight) return 0;
  const navigationBar = Platform.OS === 'android' ? insets.bottom : 0;
  return Math.max(0, keyboardHeight + navigationBar - tabBarHeight);
}

/** Words linked in answers: activity pages, and city names to their guides. */
const LINK_TERMS: LinkTerm[] = [
  ...ACTIVITY_TERMS,
  ...catalog.destinations
    .filter((d) => d.guide_url)
    .map((d) => ({
      url: d.guide_url!,
      phrases: [...new Set([d.id.replace(/_/g, ' '), ...Object.values(d.name)].map((n) => n.toLowerCase()))],
    })),
];

const PLACES = catalog.destinations.map((d) => ({
  id: d.id,
  names: [d.id.replace(/_/g, ' '), ...Object.values(d.name)],
}));

/** "Add this plan to My Trip" under answers that contain a day-by-day plan. */
function SavePlanButton({ text }: { text: string }) {
  const { t, locale } = useApp();
  const trip = useTrip();
  const [saved, setSaved] = useState(false);
  const plan = useMemo(() => parseItinerary(text, PLACES), [text]);
  if (!plan.length) return null;
  const save = () => {
    trip.applyPlan(
      plan.map((d) => ({
        day: d.day,
        text: d.text,
        destinations: d.destinations.map((id) => {
          const place = getDestination(id);
          return { id, title: place ? destinationName(place, locale) : id };
        }),
      })),
    );
    setSaved(true);
  };
  return saved ? (
    <Chip label={t('ai.planSaved', { n: plan.length })} icon="checkmark-circle" onPress={() => router.push('/trip')} />
  ) : (
    <Chip label={t('ai.savePlan', { n: plan.length })} icon="calendar-outline" onPress={save} selected />
  );
}
