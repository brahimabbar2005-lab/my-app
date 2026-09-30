/**
 * Authentication state. Guest mode is the default: nothing in the app
 * requires an account except saving, syncing, posting and bookings
 * (Master Plan §18, §36–37).
 */
import type { Session } from '@supabase/supabase-js';
import { createContext, type ReactNode, useContext, useEffect, useMemo, useState } from 'react';

import { supabase } from './supabase';

interface AuthState {
  available: boolean;
  session: Session | null;
  userId: string | null;
  signInWithEmail: (email: string) => Promise<{ error?: string }>;
  /** Completes an email sign-in with the 6-digit code from the same email. */
  verifyEmailCode: (email: string, code: string) => Promise<{ error?: string }>;
  signOut: () => Promise<void>;
  /** Deletes the account and all personal data server-side, then signs out. */
  deleteAccount: () => Promise<{ error?: string }>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);

  useEffect(() => {
    if (!supabase) return;
    supabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data } = supabase.auth.onAuthStateChange((_event, next) => setSession(next));
    return () => data.subscription.unsubscribe();
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      available: !!supabase,
      session,
      userId: session?.user.id ?? null,
      async signInWithEmail(email) {
        if (!supabase) return { error: 'not_configured' };
        const { error } = await supabase.auth.signInWithOtp({ email, options: { shouldCreateUser: true } });
        return error ? { error: error.message } : {};
      },
      async verifyEmailCode(email, code) {
        if (!supabase) return { error: 'not_configured' };
        const { error } = await supabase.auth.verifyOtp({ email, token: code, type: 'email' });
        return error ? { error: error.message } : {};
      },
      async signOut() {
        await supabase?.auth.signOut();
      },
      async deleteAccount() {
        if (!supabase || !session) return { error: 'not_signed_in' };
        const { error } = await supabase.rpc('delete_my_account');
        if (error) return { error: error.message };
        await supabase.auth.signOut();
        return {};
      },
    }),
    [session],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
