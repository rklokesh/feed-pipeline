// Minimal service worker: lets Android offer "Add to home screen".
// It caches nothing, so visitors always get the latest notices straight from the network.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", e => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", () => {});
