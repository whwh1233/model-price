// Canonical public origin used for shareable URLs (og tags, copy-link,
// Twitter intents). Always the production domain regardless of where
// the user is browsing.
export const PUBLIC_BASE_URL =
  import.meta.env.VITE_PUBLIC_BASE_URL || 'https://modelprice.closeai.space';
