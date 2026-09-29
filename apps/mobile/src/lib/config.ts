/**
 * Public runtime configuration (EXPO_PUBLIC_* is inlined at build time).
 *
 * Only values that are safe to ship inside the app belong here: service URLs,
 * the public app key, and the Supabase *publishable/anon* key. Service-role
 * keys, AI provider keys and affiliate secrets never reach the app
 * (Master Plan §32, §42).
 */
function env(value: string | undefined, fallback = ''): string {
  return (value ?? '').trim() || fallback;
}

export const config = {
  aiUrl: env(process.env.EXPO_PUBLIC_AI_URL, 'http://localhost:8000'),
  appKey: env(process.env.EXPO_PUBLIC_APP_KEY),
  platformUrl: env(process.env.EXPO_PUBLIC_PLATFORM_URL, 'http://localhost:8787'),
  supabaseUrl: env(process.env.EXPO_PUBLIC_SUPABASE_URL),
  supabaseAnonKey: env(process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY),
  siteUrl: 'https://comemorocco.com',
  accountDeletionUrl: 'https://comemorocco.com/account-delete/',
  privacyUrl: 'https://comemorocco.com/privacy-policy/',
  termsUrl: 'https://comemorocco.com/terms/',
  supportUrl: 'https://comemorocco.com/contact/',
} as const;

export const supabaseConfigured = Boolean(config.supabaseUrl && config.supabaseAnonKey);
