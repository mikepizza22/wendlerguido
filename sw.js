/* 5/3/1 Tracker service worker — offline app shell.
   Bump CACHE_VERSION whenever the shell changes so old caches get dropped. */
const CACHE_VERSION = 'v3';
const CACHE = `531-shell-${CACHE_VERSION}`;

/* Relative URLs resolve against the SW scope, so this works at / or /wendlerguido/. */
const SHELL = [
  './',
  './index.html',
  './manifest.webmanifest',
  './icon-192.png',
  './icon-512.png',
  './apple-touch-icon.png',
  './favicon-32.png',
];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE)
      /* individual adds, so one 404 can't fail the whole install */
      .then(c => Promise.all(SHELL.map(u => c.add(new Request(u, {cache:'reload'})).catch(()=>{}))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

/* Serve from cache immediately, refresh in the background. The app is one static
   file with no split chunks, so a version skew between shell entries is impossible. */
function staleWhileRevalidate(req, fallbackKey){
  return caches.open(CACHE).then(cache =>
    cache.match(req, {ignoreSearch:true}).then(hit => {
      const fetching = fetch(req).then(res => {
        if(res && res.ok && res.type === 'basic') cache.put(req, res.clone());
        return res;
      }).catch(() => null);

      if(hit){ fetching; return hit; }            // cached: use it, let the refresh land for next launch
      return fetching.then(res => res || (fallbackKey ? cache.match(fallbackKey) : undefined));
    })
  );
}

self.addEventListener('fetch', e => {
  const req = e.request;
  if(req.method !== 'GET') return;
  if(new URL(req.url).origin !== self.location.origin) return;
  if(req.headers.has('range')) return;

  /* Navigations fall back to the cached shell when both network and cache-key miss. */
  const isNav = req.mode === 'navigate';
  e.respondWith(staleWhileRevalidate(req, isNav ? './index.html' : null));
});

/* Lets the page trigger an immediate takeover after an update. */
self.addEventListener('message', e => {
  if(e.data === 'skip-waiting') self.skipWaiting();
});
