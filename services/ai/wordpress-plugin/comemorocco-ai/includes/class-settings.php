<?php
/**
 * Settings screen for the ComeMorocco AI plugin.
 *
 * @package ComeMorocco_AI
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class ComeMorocco_AI_Settings {

	const OPTION = 'comemorocco_ai_settings';

	public function __construct() {
		add_action( 'admin_menu', array( $this, 'add_menu' ) );
		add_action( 'admin_init', array( $this, 'register' ) );
	}

	/**
	 * Read one setting with a fallback.
	 *
	 * @param string $key     Setting name.
	 * @param mixed  $default Value when unset.
	 * @return mixed
	 */
	public static function get( $key, $default = '' ) {
		$settings = get_option( self::OPTION, array() );
		return isset( $settings[ $key ] ) ? $settings[ $key ] : $default;
	}

	public function add_menu() {
		add_options_page(
			__( 'ComeMorocco AI', 'comemorocco-ai' ),
			__( 'ComeMorocco AI', 'comemorocco-ai' ),
			'manage_options',
			'comemorocco-ai',
			array( $this, 'render' )
		);
	}

	public function register() {
		register_setting(
			'comemorocco_ai',
			self::OPTION,
			array( 'sanitize_callback' => array( $this, 'sanitize' ) )
		);
	}

	/**
	 * Sanitize every field. The API base is validated as a URL because it is
	 * printed into a script tag.
	 *
	 * @param array $input Raw input.
	 * @return array
	 */
	public function sanitize( $input ) {
		$clean = array();

		$clean['api_base']        = esc_url_raw( trim( (string) ( $input['api_base'] ?? '' ) ) );
		$clean['widget_key']      = sanitize_text_field( $input['widget_key'] ?? '' );
		$clean['sync_secret']     = sanitize_text_field( $input['sync_secret'] ?? '' );
		$clean['enabled']         = empty( $input['enabled'] ) ? 0 : 1;
		$clean['respect_consent'] = empty( $input['respect_consent'] ) ? 0 : 1;
		$clean['position']        = in_array( $input['position'] ?? 'right', array( 'left', 'right' ), true )
			? $input['position']
			: 'right';

		$clean['exclude_paths'] = sanitize_textarea_field( $input['exclude_paths'] ?? '' );

		$allowed_types       = get_post_types( array( 'public' => true ) );
		$submitted           = (array) ( $input['post_types'] ?? array() );
		$clean['post_types'] = array_values( array_intersect( $submitted, array_keys( $allowed_types ) ) );

		if ( empty( $clean['sync_secret'] ) ) {
			$clean['sync_secret'] = wp_generate_password( 32, false );
		}

		return $clean;
	}

	public function render() {
		if ( ! current_user_can( 'manage_options' ) ) {
			return;
		}

		$api_base    = self::get( 'api_base' );
		$post_types  = (array) self::get( 'post_types', array( 'post', 'page' ) );
		$public_types = get_post_types( array( 'public' => true ), 'objects' );
		?>
		<div class="wrap">
			<h1><?php esc_html_e( 'ComeMorocco AI', 'comemorocco-ai' ); ?></h1>

			<?php if ( empty( $api_base ) ) : ?>
				<div class="notice notice-warning">
					<p><?php esc_html_e( 'Set the service URL below. The widget will not load until it is set.', 'comemorocco-ai' ); ?></p>
				</div>
			<?php else : ?>
				<?php $this->render_status( $api_base ); ?>
			<?php endif; ?>

			<form method="post" action="options.php">
				<?php settings_fields( 'comemorocco_ai' ); ?>
				<table class="form-table" role="presentation">

					<tr>
						<th scope="row"><?php esc_html_e( 'Show the assistant', 'comemorocco-ai' ); ?></th>
						<td>
							<label>
								<input type="checkbox" name="comemorocco_ai_settings[enabled]" value="1"
									<?php checked( 1, (int) self::get( 'enabled' ) ); ?>>
								<?php esc_html_e( 'Show the chat widget to visitors', 'comemorocco-ai' ); ?>
							</label>
							<p class="description">
								<?php esc_html_e( 'Turn this off to hide the widget without deactivating the plugin.', 'comemorocco-ai' ); ?>
							</p>
						</td>
					</tr>

					<tr>
						<th scope="row">
							<label for="cmai-api"><?php esc_html_e( 'Service URL', 'comemorocco-ai' ); ?></label>
						</th>
						<td>
							<input id="cmai-api" type="url" class="regular-text" required
								name="comemorocco_ai_settings[api_base]"
								value="<?php echo esc_attr( $api_base ); ?>"
								placeholder="https://ai.comemorocco.com">
							<p class="description">
								<?php esc_html_e( 'Where the ComeMorocco AI service runs. No trailing slash.', 'comemorocco-ai' ); ?>
							</p>
						</td>
					</tr>

					<tr>
						<th scope="row">
							<label for="cmai-key"><?php esc_html_e( 'Widget key', 'comemorocco-ai' ); ?></label>
						</th>
						<td>
							<input id="cmai-key" type="text" class="regular-text"
								name="comemorocco_ai_settings[widget_key]"
								value="<?php echo esc_attr( self::get( 'widget_key' ) ); ?>">
							<p class="description">
								<?php esc_html_e( 'Must match WIDGET_KEY on the service. This key is visible to visitors — it limits casual abuse, it is not a password.', 'comemorocco-ai' ); ?>
							</p>
						</td>
					</tr>

					<tr>
						<th scope="row"><?php esc_html_e( 'Position', 'comemorocco-ai' ); ?></th>
						<td>
							<select name="comemorocco_ai_settings[position]">
								<option value="right" <?php selected( 'right', self::get( 'position', 'right' ) ); ?>>
									<?php esc_html_e( 'Bottom right', 'comemorocco-ai' ); ?>
								</option>
								<option value="left" <?php selected( 'left', self::get( 'position', 'right' ) ); ?>>
									<?php esc_html_e( 'Bottom left', 'comemorocco-ai' ); ?>
								</option>
							</select>
						</td>
					</tr>

					<tr>
						<th scope="row"><?php esc_html_e( 'Show on', 'comemorocco-ai' ); ?></th>
						<td>
							<?php foreach ( $public_types as $type ) : ?>
								<label style="display:block;margin-bottom:4px">
									<input type="checkbox" name="comemorocco_ai_settings[post_types][]"
										value="<?php echo esc_attr( $type->name ); ?>"
										<?php checked( in_array( $type->name, $post_types, true ) ); ?>>
									<?php echo esc_html( $type->labels->name ); ?>
								</label>
							<?php endforeach; ?>
						</td>
					</tr>

					<tr>
						<th scope="row">
							<label for="cmai-exclude"><?php esc_html_e( 'Hide on these paths', 'comemorocco-ai' ); ?></label>
						</th>
						<td>
							<textarea id="cmai-exclude" rows="4" class="large-text code"
								name="comemorocco_ai_settings[exclude_paths]"><?php
								echo esc_textarea( self::get( 'exclude_paths' ) );
							?></textarea>
							<p class="description">
								<?php esc_html_e( 'One path prefix per line. A chat launcher over a checkout step costs conversions.', 'comemorocco-ai' ); ?>
							</p>
						</td>
					</tr>

					<tr>
						<th scope="row"><?php esc_html_e( 'Cookie consent', 'comemorocco-ai' ); ?></th>
						<td>
							<label>
								<input type="checkbox" name="comemorocco_ai_settings[respect_consent]" value="1"
									<?php checked( 1, (int) self::get( 'respect_consent', 1 ) ); ?>>
								<?php esc_html_e( 'Wait for analytics consent before loading the widget', 'comemorocco-ai' ); ?>
							</label>
							<p class="description">
								<?php esc_html_e( 'The widget stores a session id in localStorage so conversations survive a page change. With this on, it loads only after your consent banner signals acceptance.', 'comemorocco-ai' ); ?>
							</p>
						</td>
					</tr>

					<tr>
						<th scope="row"><?php esc_html_e( 'Content sync secret', 'comemorocco-ai' ); ?></th>
						<td>
							<input type="text" class="regular-text code" readonly
								name="comemorocco_ai_settings[sync_secret]"
								value="<?php echo esc_attr( self::get( 'sync_secret' ) ); ?>">
							<p class="description">
								<?php esc_html_e( 'Used by the export endpoint so the service can pull published content. Keep it private.', 'comemorocco-ai' ); ?>
							</p>
						</td>
					</tr>

				</table>
				<?php submit_button(); ?>
			</form>

			<h2><?php esc_html_e( 'Content export', 'comemorocco-ai' ); ?></h2>
			<p><?php esc_html_e( 'The service reads published content from this endpoint to keep its knowledge base current:', 'comemorocco-ai' ); ?></p>
			<p><code><?php echo esc_html( rest_url( 'comemorocco-ai/v1/content' ) ); ?></code></p>
			<p class="description">
				<?php esc_html_e( 'Run scripts/wp_sync.py on the service host, or schedule it nightly. Publishing or editing a post also pings the service to re-index.', 'comemorocco-ai' ); ?>
			</p>
		</div>
		<?php
	}

	/**
	 * Live health check, so a misconfigured URL is visible here rather than
	 * discovered by a visitor.
	 *
	 * @param string $api_base Service URL.
	 */
	private function render_status( $api_base ) {
		$response = wp_remote_get(
			trailingslashit( $api_base ) . 'health',
			array( 'timeout' => 5 )
		);

		if ( is_wp_error( $response ) ) {
			printf(
				'<div class="notice notice-error"><p>%s <code>%s</code></p></div>',
				esc_html__( 'The service is not reachable:', 'comemorocco-ai' ),
				esc_html( $response->get_error_message() )
			);
			return;
		}

		$code = wp_remote_retrieve_response_code( $response );
		if ( 200 !== $code ) {
			printf(
				'<div class="notice notice-error"><p>%s (HTTP %d)</p></div>',
				esc_html__( 'The service responded with an error.', 'comemorocco-ai' ),
				(int) $code
			);
			return;
		}

		$body = json_decode( wp_remote_retrieve_body( $response ), true );
		$items = isset( $body['knowledge']['content_items'] ) ? (int) $body['knowledge']['content_items'] : 0;
		$model = ! empty( $body['model_configured'] );

		printf(
			'<div class="notice notice-%s"><p>%s %s</p></div>',
			$model ? 'success' : 'warning',
			esc_html( sprintf(
				/* translators: %d: number of indexed pages */
				__( 'Service reachable. %d pages indexed.', 'comemorocco-ai' ),
				$items
			) ),
			$model
				? ''
				: esc_html__( 'The model is not configured on the service, so answers will fall back.', 'comemorocco-ai' )
		);
	}
}
