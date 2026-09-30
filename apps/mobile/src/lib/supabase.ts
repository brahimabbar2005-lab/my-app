/**
 * Supabase client — only created when the project URL and publishable key are
 * configured. Without them the app runs in guest mode with mock data.
 */
import 'react-native-url-polyfill/auto';

import AsyncStorage from '@react-native-async-storage/async-storage';
import { createClient, type SupabaseClient } from '@supabase/supabase-js';
import { Platform } from 'react-native';

import { config, supabaseConfigured } from './config';

// Web pages are also rendered on the server, where there is no browser
// storage to hold a session: keep the client off there (guest render).
const serverRender = Platform.OS === 'web' && typeof window === 'undefined';

export const supabase: SupabaseClient | null =
  supabaseConfigured && !serverRender
    ? createClient(config.supabaseUrl, config.supabaseAnonKey, {
        auth: {
          storage: AsyncStorage,
          autoRefreshToken: true,
          persistSession: true,
          detectSessionInUrl: Platform.OS === 'web',
        },
      })
    : null;

export async function accessToken(): Promise<string | null> {
  if (!supabase) return null;
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}
