/**
 * Small persisted key/value store for preferences. Never throws: storage can
 * be unavailable (private browsing, quota), and the app must still work.
 */
import AsyncStorage from '@react-native-async-storage/async-storage';

const PREFIX = 'cm:';

export async function readJson<T>(key: string, fallback: T): Promise<T> {
  try {
    const raw = await AsyncStorage.getItem(PREFIX + key);
    return raw == null ? fallback : (JSON.parse(raw) as T);
  } catch {
    return fallback;
  }
}

export async function writeJson(key: string, value: unknown): Promise<void> {
  try {
    await AsyncStorage.setItem(PREFIX + key, JSON.stringify(value));
  } catch {
    // Preferences are a convenience; losing one is not an error.
  }
}

export async function removeKeys(keys: string[]): Promise<void> {
  try {
    await AsyncStorage.multiRemove(keys.map((k) => PREFIX + k));
  } catch {
    // ignore
  }
}
