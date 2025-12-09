// Service Worker Básico para PWA
self.addEventListener('install', (event) => {
    console.log('Service Worker: Instalado');
});

self.addEventListener('fetch', (event) => {
    // Esto permite que la app funcione "offline" cargando lo que pueda
    event.respondWith(fetch(event.request));
});
