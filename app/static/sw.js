// PULS-R Service Worker — app shell caching
const CACHE_NAME = 'puls-r-v1';
const ASSETS = [
  '/',
  '/static/tokens.css',
  '/static/style.css',
  '/static/app.js',
  '/static/pages.js',
  '/static/manifest.json',
];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE_NAME).then(c => c.addAll(ASSETS)).catch(() => {}));
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))));
  self.clients.claim();
});

self.addEventListener('fetch', (e) => {
  // Network-first for API, cache-first for static
  if (e.request.url.includes('/api/') || e.request.url.includes('/stream')) {
    return; // Don't cache API calls
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