/**
 * FIRINGup Service Worker
 * Provides offline capabilities and improved mobile performance
 */

const CACHE_NAME = 'firingup-v2-scanner';
const urlsToCache = [
  '/',
  '/static/css/style.css',
  '/static/js/dashboard.js',
  '/static/js/barcode_scanner.js',
  '/static/js/sales_tracking_ui.js',
  '/static/js/layer4_sales.js',
  '/static/js/sales_analytics.js'
];

// Install event - cache resources
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('Service Worker: Caching files');
        return cache.addAll(urlsToCache);
      })
      .catch(err => {
        console.log('Service Worker: Cache failed', err);
      })
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cache => {
          if (cache !== CACHE_NAME) {
            console.log('Service Worker: Clearing old cache');
            return caches.delete(cache);
          }
        })
      );
    })
  );
});

// Fetch event - serve from cache when offline
self.addEventListener('fetch', event => {
  // Skip cache for API calls - always fetch from network
  if (event.request.url.includes('/api/')) {
    event.respondWith(fetch(event.request));
    return;
  }

  event.respondWith(
    caches.match(event.request)
      .then(response => {
        // Return cached version or fetch from network
        return response || fetch(event.request);
      })
      .catch(() => {
        // Offline fallback
        console.log('Service Worker: Fetch failed, serving offline page');
      })
  );
});
