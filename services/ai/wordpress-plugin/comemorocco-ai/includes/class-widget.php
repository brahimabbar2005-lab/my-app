<?php
/**
 * Renders the chat widget on the front end.
 *
 * @package ComeMorocco_AI
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class ComeMorocco_AI_Widget {

	public function __construct() {
		add_action( 'wp_enqueue_scripts', array( $this, 'enqueue' ) );
		add_shortcode( 'comemorocco_ai', array( $this, 'shortcode' ) );
	}

	/**
	 * Whether the widget should render on the current request.
	 *
	 * @return bool
	 */
	private function should_render() {
		if ( ! ComeMorocco_AI_Settings::get( 'enabled' ) ) {
			return false;
		}
		if ( ! ComeMorocco_AI_Settings::get( 'api_base' ) ) {
			return false;
		}
		// A chat launcher on an admin screen or a feed helps nobody.
		if ( is_admin() || is_feed() || is_embed() ) {
			return false;
		}

		$path = wp_parse_url( add_query_arg( array() ), PHP_URL_PATH );
		$path = $path ? $path : '/';

		$excluded = array_filter( array_map( 'trim', explode( "\n", (string) ComeMorocco_AI_Settings::get( 'exclude_paths' ) ) ) );
		foreach ( $excluded as $prefix ) {
			if ( '' !== $prefix && 0 === strpos( $path, $prefix ) ) {
				return false;
			}
		}

		if ( is_singular() ) {
			$allowed = (array) ComeMorocco_AI_Settings::get( 'post_types', array( 'post', 'page' ) );
			if ( ! in_array( get_post_type(), $allowed, true ) ) {
				return false;
			}
		}

		/**
		 * Allow themes to suppress the widget on specific templates.
		 *
		 * @param bool $render Whether to render.
		 */
		return (bool) apply_filters( 'comemorocco_ai_should_render', true );
	}

	/**
	 * Two-letter language code for the current request, so the assistant
	 * answers in the language the page is written in by default.
	 *
	 * @return string
	 */
	private function locale() {
		$locale = function_exists( 'pll_current_language' )
			? pll_current_language()          // Polylang
			: substr( get_locale(), 0, 2 );   // core
		return sanitize_key( substr( (string) $locale, 0, 2 ) ) ?: 'en';
	}

	public function enqueue() {
		if ( ! $this->should_render() ) {
			return;
		}

		wp_enqueue_script(
			'comemorocco-ai',
			COMEMOROCCO_AI_URL . 'assets/comemorocco-ai.js',
			array(),
			COMEMOROCCO_AI_VERSION,
			true
		);

		$config = array(
			'apiBase'   => untrailingslashit( ComeMorocco_AI_Settings::get( 'api_base' ) ),
			'widgetKey' => ComeMorocco_AI_Settings::get( 'widget_key' ),
			'position'  => ComeMorocco_AI_Settings::get( 'position', 'right' ),
			'locale'    => $this->locale(),
			'consent'   => (bool) ComeMorocco_AI_Settings::get( 'respect_consent', 1 ),
		);

		wp_add_inline_script(
			'comemorocco-ai',
			$this->bootstrap_script( $config ),
			'after'
		);
	}

	/**
	 * Inline bootstrap.
	 *
	 * When consent is required the widget waits for a signal rather than
	 * loading immediately, because it writes a session id to localStorage.
	 * Both the common consent events and a manual API are supported, so this
	 * works with most banners without a per-vendor integration.
	 *
	 * @param array $config Widget configuration.
	 * @return string
	 */
	private function bootstrap_script( array $config ) {
		$json = wp_json_encode( $config );

		return <<<JS
(function () {
	var config = {$json};

	function start() {
		if (window.__cmAiStarted || !window.ComeMoroccoAI) return;
		window.__cmAiStarted = true;
		window.ComeMoroccoAI.init(config);
	}

	if (!config.consent) {
		start();
		return;
	}

	// Already granted before this script ran.
	if (window.cmAiConsentGranted === true) {
		start();
		return;
	}

	// Common consent-banner events. Harmless if none of them ever fire.
	['cmAiConsent', 'cookie_consent_accepted', 'cookieyes-consent-update',
	 'CookiebotOnAccept', 'complianz_status_update'].forEach(function (name) {
		window.addEventListener(name, start);
		document.addEventListener(name, start);
	});

	// Manual hook for a custom banner: window.ComeMoroccoAIConsent()
	window.ComeMoroccoAIConsent = start;
})();
JS;
	}

	/**
	 * [comemorocco_ai] renders nothing on its own — the widget is a fixed
	 * launcher — but the shortcode lets an editor force it onto a page that
	 * the post-type rules would otherwise exclude.
	 *
	 * @return string
	 */
	public function shortcode() {
		if ( ! wp_script_is( 'comemorocco-ai', 'enqueued' ) ) {
			add_filter( 'comemorocco_ai_should_render', '__return_true' );
			$this->enqueue();
		}
		return '';
	}
}
