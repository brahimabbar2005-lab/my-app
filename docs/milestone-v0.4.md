# Milestone v0.4 — Admin catalogue, stays, phone-test fixes

## What shipped
- **Admin catalogue.** Profile & settings → **Manage offers** (admins only). Admins add and edit hotels, riads, hostels, guesthouses, desert camps, apartments, villas, tours, day trips, activities, classes, cars, transfers and drivers. Each offer has:
  - city
  - short label and description
  - price from (MAD)
  - photo
  - booking link
  - status (draft / published / archived)
  The database functions `admin_listings()` and `admin_save_listing()` refuse non-admins, and every save is audited (migration `20261002000007_admin_catalog.sql`).
- **Links.** A **partner (affiliate) link** is kept private in `affiliate_links` and opened through the platform worker's tracked `/go` redirect. A **direct link** (the riad's own booking page) is public and opened as is.
- **Stays in the app.** The Book tab and city pages load published offers from Supabase on top of the bundled partners. They have type chips (Hotels, Riads, Hostels…), city chips for every category, and prices.
- **AI.**
  - "Add this N-day plan to My Trip" under day-by-day plans.
  - Activity words and city names link to comemorocco.com pages.
  - The AI no longer claims to have saved anything.
  - Photos from Unsplash when asked.
- **Near me.** Uses the phone's location (permission first) to open the nearest city.
- **Photos.** City pages, city tiles, guide cards and activities use the site's own photos.
- **AI tab.** The composer is lifted by the keyboard height (Android edge-to-edge).

## Verification
- **Database:** RLS tests, 9 new checks.
  - non-admins can't save or list
  - drafts are visible to admins only
  - partner links stay private, and switching to a direct link drops the partner link
  - non-https links are refused
  - saves are audited
- **Setup file:** `supabase/setup/all-in-one.sql` rebuilt and verified on an empty Postgres 16.
- **Unit tests:** itinerary parsing (en/fr/es/ar), plan saving, answer links, Near me distances, admin drafts.
- **Browser** (simulated server answers):
  - add a riad as admin, then see it under Book → Stays → Riad with its price
  - plan button and answer links
  - AI photos with credits
  - no console errors

## To switch it on in the live project
Supabase → SQL Editor → New query → paste `supabase/migrations/20261002000007_admin_catalog.sql` → Run.
