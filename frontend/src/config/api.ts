export const API_V2_BASE = import.meta.env.VITE_API_V2_BASE || '/api/v2';

// Canonical public origin used for shareable URLs (og tags, copy-link,
// Twitter intents). Always the production domain regardless of where
// the user is browsing.
export const PUBLIC_BASE_URL =
  import.meta.env.VITE_PUBLIC_BASE_URL || 'https://modelprice.boxtech.icu';
