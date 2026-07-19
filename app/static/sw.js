// PULS-R Service Worker — app shell caching
// SECURITY (T3-0): NEVER cache authenticated /app/* HTML — it bakes the
// per-user window.API_KEY into the markup. Caching it would serve one user's
// dashboard (with their key + data) to another user. Only cache true static
// assets (css/js/img/manifest). Bump CACHE_NAME on any change to force purge.
const CACHE_NAME = 'puls-r-v2';
const ASSETS = [
  '/',
  '/static/tokens.css',
  '/static/style.css',
  '/static/manifest.json',
  '/static/sw.js',
];

function isCacheableStatic(url) {
  // Only same-origin GETs for static asset paths.
  if (url.startsWith('http://') || url.startsWith('https://')) {
    try {
      const u = new URL(url);
      if (u.origin !== self.location.origin) return false;
    } catch (_) { return false; }
  }
  // Authenticated app HTML must always be network-fetched (per-user key).
  if (url.includes('/app/')) return false;
  if (url.includes('/api/') || url.includes('/stream')) return false;
  return true;
}

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE_NAME).then(c => c.addAll(ASSETS)).catch(() => {}));
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))));
  self.clients.claim();
});

self.addEventListener('fetch', (e) => {
  const url = e.request.url;
  // Never cache API/stream or authenticated app HTML.
  if (url.includes('/api/') || url.includes('/stream') || url.includes('/app/')) {
    return; // network only
  }
  if (!isCacheableStatic(url) || e.request.method !== 'GET') {
    return; // network only
  }
  e.respondWith(
    caches.match(e.request).then(cached => {
      return cached || fetch(e.request).then(resp => {
        if (resp.ok && e.request.method === 'GET') {
          const clone = resp.clone();
          caches.open(CACHE_NAME).then(c => c.put(e.request, clone));
        }
        return resp;
      }).catch(() => cached);
    })
  );
});
