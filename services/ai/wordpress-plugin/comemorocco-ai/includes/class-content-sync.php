<?php
/**
 * Content export for the AI knowledge base.
 *
 * Exposes published content in the shape the service's content map uses, and
 * pings the service when something is published, updated or removed so the
 * index does not drift from the site (02_MVP_SCOPE §35).
 *
 * @package ComeMorocco_AI
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class ComeMorocco_AI_Content_Sync {

	public function __construct() {
		add_action( 'rest_api_init', array( $this, 'register_routes' ) );

		// Re-index triggers. Scheduled rather than immediate so an editor
		// saving a post is never waiting on an HTTP call to another host.
		add_action( 'transition_post_status', array( $this, 'on_status_change' ), 10, 3 );
		add_action( 'before_delete_post', array( $this, 'on_delete' ) );
		add_action( 'comemorocco_ai_notify_change', array( $this, 'notify_service' ) );
	}

	public function register_routes() {
		register_rest_route(
			'comemorocco-ai/v1',
			'/content',
			array(
				'methods'             => 'GET',
				'callback'            => array( $this, 'export' ),
				'permission_callback' => array( $this, 'check_secret' ),
				'args'                => array(
					'page'     => array( 'default' => 1, 'sanitize_callback' => 'absint' ),
					'per_page' => array( 'default' => 50, 'sanitize_callback' => 'absint' ),
					'since'    => array( 'default' => '', 'sanitize_callback' => 'sanitize_text_field' ),
				),
			)
		);
	}

	/**
	 * The export contains full post content, so it is not public.
	 *
	 * @param WP_REST_Request $request Request.
	 * @return bool
	 */
	public function check_secret( $request ) {
		$expected = (string) ComeMorocco_AI_Settings::get( 'sync_secret' );
		$provided = (string) $request->get_header( 'x-sync-secret' );

		if ( '' === $expected || '' === $provided ) {
			return false;
		}
		return hash_equals( $expected, $provided );
	}

	/**
	 * Export published content in content-map shape.
	 *
	 * @param WP_REST_Request $request Request.
	 * @return WP_REST_Response
	 */
	public function export( $request ) {
		$args = array(
			'post_type'      => (array) ComeMorocco_AI_Settings::get( 'post_types', array( 'post', 'page' ) ),
			'post_status'    => 'publish',
			'posts_per_page' => min( (int) $request['per_page'], 100 ),
			'paged'          => max( 1, (int) $request['page'] ),
			'orderby'        => 'modified',
			'order'          => 'DESC',
		);

		if ( ! empty( $request['since'] ) ) {
			$args['date_query'] = array(
				array(
					'column' => 'post_modified_gmt',
					'after'  => $request['since'],
				),
			);
		}

		$query = new WP_Query( $args );
		$items = array();

		foreach ( $query->posts as $post ) {
			$items[] = $this->shape( $post );
		}

		return new WP_REST_Response(
			array(
				'items'       => $items,
				'page'        => (int) $args['paged'],
				'total_pages' => (int) $query->max_num_pages,
				'total'       => (int) $query->found_posts,
				'exported_at' => gmdate( 'c' ),
			),
			200
		);
	}

	/**
	 * One post as the knowledge base expects it.
	 *
	 * Rank Math fields are read where present so the SEO title and description
	 * — which are usually the best one-line summary of a page — reach the
	 * retriever.
	 *
	 * @param WP_Post $post Post.
	 * @return array
	 */
	private function shape( $post ) {
		$terms = wp_get_post_terms( $post->ID, 'category', array( 'fields' => 'names' ) );
		$tags  = wp_get_post_terms( $post->ID, 'post_tag', array( 'fields' => 'names' ) );

		return array(
			'id'               => (string) $post->ID,
			'title'            => get_the_title( $post ),
			'url'              => get_permalink( $post ),
			'excerpt'          => wp_strip_all_tags( get_the_excerpt( $post ) ),
			'content'          => wp_strip_all_tags( strip_shortcodes( $post->post_content ) ),
			'seo_title'        => (string) get_post_meta( $post->ID, 'rank_math_title', true ),
			'seo_description'  => (string) get_post_meta( $post->ID, 'rank_math_description', true ),
			'focus_keywords'   => array_filter( array_map(
				'trim',
				explode( ',', (string) get_post_meta( $post->ID, 'rank_math_focus_keyword', true ) )
			) ),
			'categories'       => is_wp_error( $terms ) ? array() : $terms,
			'tags'             => is_wp_error( $tags ) ? array() : $tags,
			'post_type'        => $post->post_type,
			'created_at'       => get_post_time( 'c', true, $post ),
			'updated_at'       => get_post_modified_time( 'c', true, $post ),
		);
	}

	/**
	 * Schedule a re-index when content becomes, or stops being, published.
	 *
	 * @param string  $new_status New status.
	 * @param string  $old_status Old status.
	 * @param WP_Post $post       Post.
	 */
	public function on_status_change( $new_status, $old_status, $post ) {
		if ( $new_status === $old_status ) {
			return;
		}
		if ( 'publish' !== $new_status && 'publish' !== $old_status ) {
			return;
		}
		$allowed = (array) ComeMorocco_AI_Settings::get( 'post_types', array( 'post', 'page' ) );
		if ( ! in_array( $post->post_type, $allowed, true ) ) {
			return;
		}
		$this->schedule();
	}

	/**
	 * A deleted page must stop being recommended, or the assistant will send
	 * travellers to a 404.
	 *
	 * @param int $post_id Post id.
	 */
	public function on_delete( $post_id ) {
		$post = get_post( $post_id );
		if ( $post && 'publish' === $post->post_status ) {
			$this->schedule();
		}
	}

	/**
	 * Debounce: one notification per minute however many posts are saved.
	 */
	private function schedule() {
		if ( ! wp_next_scheduled( 'comemorocco_ai_notify_change' ) ) {
			wp_schedule_single_event( time() + 60, 'comemorocco_ai_notify_change' );
		}
	}

	/**
	 * Tell the service that content changed. Fire and forget: a failure here
	 * must never surface to an editor, and the nightly sync is the backstop.
	 */
	public function notify_service() {
		$api_base = ComeMorocco_AI_Settings::get( 'api_base' );
		$secret   = ComeMorocco_AI_Settings::get( 'sync_secret' );

		if ( empty( $api_base ) || empty( $secret ) ) {
			return;
		}

		wp_remote_post(
			untrailingslashit( $api_base ) . '/api/admin/content-changed',
			array(
				'timeout'  => 5,
				'blocking' => false,
				'headers'  => array(
					'Content-Type'  => 'application/json',
					'X-Sync-Secret' => $secret,
				),
				'body'     => wp_json_encode( array( 'source' => home_url(), 'at' => gmdate( 'c' ) ) ),
			)
		);
	}
}
