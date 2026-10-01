/**
 * Public runtime configuration (EXPO_PUBLIC_* is inlined at build time).
 *
 * Only values that are safe to ship inside the app belong here: service URLs,
 * the public app key, and the Supabase *publishable/anon* key. Service-role
 * keys, AI provider keys and affiliate secrets never reach the app
 * (Master Plan §32, §42).
 */
import Constants from 'expo-constants';
import { NativeModules, Platform } from 'react-native';

import { devHostUrl } from './dev-host';

function env(value: string | undefined, fallback = ''): string {
  return (value ?? '').trim() || fallback;
}

/** Where the development server runs, as "host:port". Expo reports it in
 * several places depending on SDK and client; the bundle URL always has it. */
function devServerHost(): string | null {
  if (!__DEV__) return null;
  const goConfig = Constants.expoGoConfig as { debuggerHost?: string } | null;
  const scriptUrl: string | undefined = NativeModules.SourceCode?.scriptURL ?? NativeModules.SourceCode?.getConstants?.().scriptURL;
  const fromScript = scriptUrl?.match(/^[a-z]+:\/\/([^/]+)/i)?.[1];
  return Constants.expoConfig?.hostUri ?? goConfig?.debuggerHost ?? fromScript ?? null;
}

const hostUri = devServerHost();

export const config = {
  aiUrl: devHostUrl(env(process.env.EXPO_PUBLIC_AI_URL, 'http://localhost:8000'), hostUri, Platform.OS),
  appKey: env(process.env.EXPO_PUBLIC_APP_KEY),
  platformUrl: devHostUrl(env(process.env.EXPO_PUBLIC_PLATFORM_URL, 'http://localhost:8787'), hostUri, Platform.OS),
  supabaseUrl: env(process.env.EXPO_PUBLIC_SUPABASE_URL),
  supabaseAnonKey: env(process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY),
  siteUrl: 'https://comemorocco.com',
  accountDeletionUrl: 'https://comemorocco.com/account-delete/',
  privacyUrl: 'https://comemorocco.com/privacy-policy/',
  termsUrl: 'https://comemorocco.com/terms/',
  supportUrl: 'https://comemorocco.com/contact/',
} as const;

export const supabaseConfigured = Boolean(config.supabaseUrl && config.supabaseAnonKey);
