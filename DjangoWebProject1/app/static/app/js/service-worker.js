const CACHE_NAME = 'mastertool-v1';
const STATIC_CACHE = 'mastertool-static-v1';
const DYNAMIC_CACHE = 'mastertool-dynamic-v1';

// Статические ресурсы для кэширования
const STATIC_ASSETS = [
    '/',
    '/catalog/',
    '/cart/',
    '/static/app/manifest.json',
    '/static/app/css/theme.css',
    '/static/app/css/main.css',
];

// Установка Service Worker
self.addEventListener('install', (event) => {
    console.log('[SW] Installing Service Worker ...');
    
    event.waitUntil(
        caches.open(STATIC_CACHE)
            .then((cache) => {
                console.log('[SW] Caching static assets');
                return cache.addAll(STATIC_ASSETS);
            })
            .then(() => self.skipWaiting())
            .catch((err) => console.log('[SW] Cache error:', err))
    );
});

// Активация Service Worker
self.addEventListener('activate', (event) => {
    console.log('[SW] Activating Service Worker ....');
    
    event.waitUntil(
        caches.keys().then((keyList) => {
            return Promise.all(
                keyList.map((key) => {
                    if (key !== STATIC_CACHE && key !== DYNAMIC_CACHE && key !== CACHE_NAME) {
                        console.log('[SW] Removing old cache:', key);
                        return caches.delete(key);
                    }
                })
            );
        }).then(() => self.clients.claim())
    );
});

// Перехват запросов
self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);

    // Пропускаем запросы к API и внешним ресурсам
    if (url.origin !== location.origin) {
        return;
    }

    // Стратегия: Stale-while-revalidate для HTML страниц
    if (request.mode === 'navigate' || request.headers.get('accept').includes('text/html')) {
        event.respondWith(
            caches.open(DYNAMIC_CACHE).then((cache) => {
                return cache.match(request).then((cachedResponse) => {
                    const fetchPromise = fetch(request).then((networkResponse) => {
                        cache.put(request, networkResponse.clone());
                        return networkResponse;
                    }).catch(() => {
                        // Если нет интернета и есть кэш - возвращаем кэш
                        if (cachedResponse) {
                            return cachedResponse;
                        }
                        // Иначе возвращаем страницу offline
                        return caches.match('/offline/');
                    });
                    
                    return cachedResponse || fetchPromise;
                });
            })
        );
        return;
    }

    // Стратегия: Cache-first для статики (CSS, JS, Images, Fonts)
    if (
        request.destination === 'style' ||
        request.destination === 'script' ||
        request.destination === 'image' ||
        request.destination === 'font'
    ) {
        event.respondWith(
            caches.match(request).then((cachedResponse) => {
                if (cachedResponse) {
                    return cachedResponse;
                }
                
                return fetch(request).then((networkResponse) => {
                    return caches.open(STATIC_CACHE).then((cache) => {
                        cache.put(request, networkResponse.clone());
                        return networkResponse;
                    });
                });
            })
        );
        return;
    }

    // Default: Network-first для остального
    event.respondWith(
        fetch(request)
            .then((response) => {
                return response;
            })
            .catch(() => {
                return caches.match(request);
            })
    );
});

// Обработка push-уведомлений (для будущего использования)
self.addEventListener('push', (event) => {
    const data = event.data ? event.data.json() : {};
    const title = data.title || 'InstrumentPSK';
    const options = {
        body: data.body || 'У вас новое уведомление',
        icon: '/static/app/images/pwa/icon-192x192.png',
        badge: '/static/app/images/pwa/icon-72x72.png',
        vibrate: [100, 50, 100],
        data: {
            url: data.url || '/'
        }
    };
    
    event.waitUntil(
        self.registration.showNotification(title, options)
    );
});

// Обработка клика по уведомлению
self.addEventListener('notificationclick', (event) => {
    event.notification.close();
    
    event.waitUntil(
        clients.openWindow(event.notification.data.url)
    );
});
