/**
 * API configuration for the frontend.
 * Values can be overridden via environment variables.
 */

export const API_BASE = import.meta.env.VITE_API_BASE || '/api';
export const API_V2_BASE = import.meta.env.VITE_API_V2_BASE || '/api/v2';
export const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';

// Canonical public origin used for shareable URLs (og tags, copy-link,
// Twitter intents). Always the production domain regardless of where
// the user is browsing — a dev hitting "Copy link" should still get a
// URL that works when pasted into a tweet.
export const PUBLIC_BASE_URL =
  import.meta.env.VITE_PUBLIC_BASE_URL || 'https://modelprice.boxtech.icu';
