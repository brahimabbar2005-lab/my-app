=== ComeMorocco AI ===
Contributors: comemorocco
Tags: ai, chat, travel, morocco, assistant
Requires at least: 6.0
Tested up to: 6.5
Requires PHP: 7.4
Stable tag: 1.0.0
License: GPLv2 or later

Morocco travel assistant for ComeMorocco.com.

== Description ==

Renders the ComeMorocco AI chat widget and connects it to the ComeMorocco AI
service. The plugin is deliberately thin: no model, no retrieval and no API
keys with spend attached to them run inside WordPress.

Features:

* Chat widget, isolated from the theme with Shadow DOM
* Per-post-type and per-path display rules
* Waits for cookie consent before loading, if required
* Content export so the assistant stays current with the site
* Automatic re-index when a post is published, updated or deleted
* English and French interface, following the page language

== Installation ==

1. Upload the folder to `/wp-content/plugins/`.
2. Activate it.
3. Go to Settings > ComeMorocco AI.
4. Enter the service URL and widget key.
5. Copy the sync secret into the service configuration.
6. Tick "Show the assistant" once the status banner is green.

== Frequently Asked Questions ==

= Does this send my content anywhere? =

The service reads published content from an authenticated endpoint on your
site to answer questions accurately. Nothing is sent without the sync secret.

= Does it work with caching plugins? =

Yes. The widget loads client-side and the answers are not cached.

= Can I hide it on some pages? =

Yes — by post type, or by path prefix, on the settings screen.

== Changelog ==

= 1.0.0 =
* First release.
