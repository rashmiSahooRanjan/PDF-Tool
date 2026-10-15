/* ===================================================================
   iLovePDF Pro — Service Worker (PWA Offline & App Support)
   =================================================================== */

const CACHE_NAME = 'ilovepdf-pro-v1';
const STATIC_ASSETS = [
  '/',
  '/editor',
  '/convert',
  '/utilities',
  '/ocr',
  '/static/css/style.css',
  '/static/css/editor.css',
  '/static/js/theme.js',
  '/static/js/app.js',
  '/static/js/editor.js',
  '/static/js/chat.js',
  '/static/manifest.json',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/vendor/pdfjs/pdf.min.js',
  '/static/vendor/pdfjs/pdf.worker.min.js'
];

// 1. Install & pre-cache shell
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS).catch((err) => {
        console.warn('PWA: Failed to precache some static assets:', err);
      });
    }).then(() => self.skipWaiting())
  );
});

// 2. Activate & cleanup old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// 3. Fetch strategy: Network-first for dynamic routes, cache-first for static assets
self.addEventListener('fetch', (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // Bypass API calls and non-GET requests from caching
  if (req.method !== 'GET' || url.pathname.startsWith('/api/')) {
    return;
  }

  // Static assets: cache-first with network refresh
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(req).then((cached) => {
        if (cached) {
          fetch(req).then((fresh) => {
            if (fresh && fresh.status === 200) {
              caches.open(CACHE_NAME).then((cache) => cache.put(req, fresh));
            }
          }).catch(() => {});
          return cached;
        }
        return fetch(req).then((fresh) => {
          if (fresh && fresh.status === 200) {
            const clone = fresh.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(req, clone));
          }
          return fresh;
        });
      })
    );
    return;
  }

  // HTML pages: network-first with cache fallback
  event.respondWith(
    fetch(req).then((fresh) => {
      if (fresh && fresh.status === 200) {
        const clone = fresh.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(req, clone));
      }
      return fresh;
    }).catch(() => caches.match(req).then((cached) => cached || caches.match('/')))
  );
});
