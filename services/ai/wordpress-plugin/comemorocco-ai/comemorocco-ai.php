<?php
/**
 * Plugin Name:       ComeMorocco AI
 * Plugin URI:        https://comemorocco.com/
 * Description:       Morocco travel assistant for ComeMorocco.com. Renders the chat widget and connects it to the ComeMorocco AI service.
 * Version:           1.0.0
 * Requires at least: 6.0
 * Requires PHP:      7.4
 * Author:            ComeMorocco
 * License:           GPL-2.0-or-later
 * Text Domain:       comemorocco-ai
 *
 * The plugin is deliberately thin. It renders a widget and stores settings.
 * No model, no retrieval, no API keys with spend attached to them live in
 * WordPress — all of that sits behind the service, where it can be rate
 * limited, monitored and updated without touching the site.
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

define( 'COMEMOROCCO_AI_VERSION', '1.0.0' );
define( 'COMEMOROCCO_AI_PATH', plugin_dir_path( __FILE__ ) );
define( 'COMEMOROCCO_AI_URL', plugin_dir_url( __FILE__ ) );

require_once COMEMOROCCO_AI_PATH . 'includes/class-settings.php';
require_once COMEMOROCCO_AI_PATH . 'includes/class-widget.php';
require_once COMEMOROCCO_AI_PATH . 'includes/class-content-sync.php';

/**
 * Boot the plugin.
 */
function comemorocco_ai_init() {
	new ComeMorocco_AI_Settings();
	new ComeMorocco_AI_Widget();
	new ComeMorocco_AI_Content_Sync();
}
add_action( 'plugins_loaded', 'comemorocco_ai_init' );

/**
 * Default options on activation.
 */
function comemorocco_ai_activate() {
	$defaults = array(
		'api_base'        => '',
		'widget_key'      => '',
		'sync_secret'     => wp_generate_password( 32, false ),
		'enabled'         => 0,
		'position'        => 'right',
		'exclude_paths'   => "/checkout\n/cart\n/my-account",
		'post_types'      => array( 'post', 'page' ),
		'respect_consent' => 1,
	);

	$existing = get_option( 'comemorocco_ai_settings', array() );
	update_option( 'comemorocco_ai_settings', array_merge( $defaults, $existing ) );
}
register_activation_hook( __FILE__, 'comemorocco_ai_activate' );

/**
 * Tidy up scheduled jobs on deactivation. Settings are kept so that
 * reactivating does not lose the configuration.
 */
function comemorocco_ai_deactivate() {
	wp_clear_scheduled_hook( 'comemorocco_ai_notify_change' );
}
register_deactivation_hook( __FILE__, 'comemorocco_ai_deactivate' );
