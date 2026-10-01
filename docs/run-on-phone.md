# Run the app on your phone (Expo Go)

The app uses only modules that are built into Expo Go, so no app-store build is needed for testing. The app runs from your computer, and your phone loads it over Wi-Fi.

## One-time setup (Mac)
1. Install **Node.js 22 or newer** from https://nodejs.org (the LTS installer).
2. Open **Terminal** and run:
   ```bash
   corepack enable
   git clone https://github.com/brahimabbar2005-lab/my-app.git comemorocco
   cd comemorocco
   git checkout claude/gifted-franklin-puuz00
   pnpm install
   ```
3. Create the app's local settings file. It holds the public (publishable) key only, never the secret key:
   ```bash
   cat > apps/mobile/.env.local <<'EOF'
   EXPO_PUBLIC_SUPABASE_URL=https://vsswwdauxyjsefuhvtgr.supabase.co
   EXPO_PUBLIC_SUPABASE_ANON_KEY=<your publishable key, sb_publishable_…>
   EOF
   ```
4. On your phone, install **Expo Go** from the App Store or Google Play.

## Every time
1. In Terminal, from the `comemorocco` folder, run:
   ```bash
   git pull
   pnpm mobile
   ```
2. A QR code appears.
   - **iPhone:** scan it with the Camera app, then tap "Open in Expo Go".
   - **Android:** scan it from inside Expo Go.
3. Phone and Mac must be on the same Wi-Fi. If the phone can't connect, stop with `Ctrl+C` and run `pnpm mobile --tunnel` instead.

## What to try
- **Sign-in:** Profile → Sign in → your email → enter the 6-digit code from the email.
- **My Trip:** save a city (the heart), add it to your trip, then check Supabase → Table Editor → `trips`.
- **Community:** post a question, reply, vote; try a post containing `wa.me/123` and it is held for review.
- **Moderation:** Profile & settings → Moderation queue (admins only).

## AI answers and partner links (optional, on the same Mac)
- **AI** (Terminal tab 2): `cd ~/comemorocco/services/ai && source .venv/bin/activate && make run-lan`.
  The private `services/ai/.env` holds the provider keys. Add `UNSPLASH_ACCESS_KEY=…` there for photos in answers.
- **"View options" partner links** (Terminal tab 3): `cd ~/comemorocco && pnpm worker:lan`.
- In development the app finds these services on the Mac by itself, as long as the phone is on the same Wi-Fi (not `--tunnel`).
