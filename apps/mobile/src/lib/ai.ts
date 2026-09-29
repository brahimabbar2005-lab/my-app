import { type AiClientOptions } from '@comemorocco/shared';
import { fetch as expoFetch } from 'expo/fetch';

import { config } from './config';
import { accessToken } from './supabase';

/** AI client options. expo/fetch can read response bodies as a stream. */
export const aiClient: AiClientOptions = {
  baseUrl: config.aiUrl,
  appKey: config.appKey || undefined,
  getAccessToken: accessToken,
  fetch: expoFetch as unknown as AiClientOptions['fetch'],
};
