// Retired: SarkariChart is a normal website, not an installable app. This removes any old copy from browsers.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", e => e.waitUntil(self.registration.unregister()));
