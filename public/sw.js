const CACHE_VERSION = 'ddgff-pwa-v1';
const STATIC_CACHE = `${CACHE_VERSION}-static`;
const RUNTIME_CACHE = `${CACHE_VERSION}-runtime`;
const APP_SCOPE = new URL(self.registration.scope);
const APP_BASE = APP_SCOPE.pathname.replace(/\/$/, '');

const basePath = (path) => `${APP_BASE}${path}`;
const CORE_ASSETS = [
  basePath('/'),
  basePath('/archive/'),
  basePath('/manifest.json'),
  basePath('/pwa-config.json'),
  basePath('/favicon/favicon.svg'),
  basePath('/icons/icon-192.png'),
  basePath('/icons/icon-512.png'),
  basePath('/icons/icon-maskable-192.png'),
  basePath('/icons/icon-maskable-512.png')
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(STATIC_CACHE)
      .then((cache) => cache.addAll(CORE_ASSETS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => !key.startsWith(CACHE_VERSION)).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin || !url.pathname.startsWith(APP_BASE)) return;

  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          caches.open(RUNTIME_CACHE).then((cache) => cache.put(request, copy));
          return response;
        })
        .catch(() => caches.match(request).then((cached) => cached || caches.match(basePath('/'))))
    );
    return;
  }

  const isStaticAsset = /\.(?:css|js|png|jpg|jpeg|webp|svg|woff2?|ttf|json|xml)$/i.test(url.pathname);
  if (!isStaticAsset) return;

  event.respondWith(
    caches.match(request).then((cached) => {
      if (cached) return cached;
      return fetch(request).then((response) => {
        if (!response || response.status !== 200) return response;
        const copy = response.clone();
        caches.open(RUNTIME_CACHE).then((cache) => cache.put(request, copy));
        return response;
      });
    })
  );
});
