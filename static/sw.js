/* Tecnocel CRM — Service Worker v1 */
const CACHE = 'tecnocel-v1';
const STATIC = [
  '/static/css/style.css',
  '/static/js/main.js',
  '/static/img/logo.png',
  '/static/img/logo.svg',
  '/offline.html',
];

/* ── Instalación: precachear recursos estáticos ── */
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE).then(cache => cache.addAll(STATIC))
  );
  self.skipWaiting();
});

/* ── Activación: limpiar versiones viejas ── */
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

/* ── Fetch: estrategia mixta ── */
self.addEventListener('fetch', event => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);
  if (url.origin !== location.origin) return;

  /* Recursos estáticos → Cache First (red como fallback) */
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(req).then(cached => {
        if (cached) return cached;
        return fetch(req).then(res => {
          const clone = res.clone();
          caches.open(CACHE).then(c => c.put(req, clone));
          return res;
        });
      })
    );
    return;
  }

  /* Páginas HTML → Network First (offline.html como fallback) */
  event.respondWith(
    fetch(req).catch(() =>
      caches.match(req).then(cached => cached || caches.match('/offline.html'))
    )
  );
});
