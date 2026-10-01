/**
 * On a phone, "localhost" is the phone itself. In development, point local
 * services at the computer running Expo instead (the host Expo Go loaded the
 * app from, e.g. 192.168.1.20). Production URLs are left untouched.
 */
export function devHostUrl(url: string, hostUri: string | null | undefined, os: string): string {
  if (os === 'web' || !hostUri) return url;
  const host = hostUri.split(':')[0] ?? '';
  // Only a computer on the same network (not an Expo tunnel host).
  if (!/^\d{1,3}(\.\d{1,3}){3}$|\.local$/.test(host)) return url;
  return url.replace(/^(https?:\/\/)(localhost|127\.0\.0\.1)(?=[:/]|$)/, `$1${host}`);
}
