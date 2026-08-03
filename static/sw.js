/*
 * Service worker minimal de la PWA "Suivi de Chantier".
 *
 * Portée volontairement limitée à ce qu'une app Streamlit peut réellement
 * offrir hors ligne : Streamlit exige une connexion WebSocket active pour la
 * moindre interaction (aucune logique métier ne tourne côté client), donc ce
 * service worker NE permet PAS de saisir une dépense hors connexion. Il :
 *   1. met en cache la "coquille" statique (icônes, manifest) pour un
 *      chargement plus rapide au lancement suivant ;
 *   2. affiche un écran "hors connexion" explicite au lieu de l'erreur brute
 *      du navigateur si le réseau est coupé ;
 *   3. prépare les événements `push`/`notificationclick` pour de futures
 *      notifications serveur (non activées : voir utils/notifications.py).
 *
 * Stratégie : "network first" pour les pages/le WebSocket (toujours la donnée
 * la plus fraîche), "cache first" seulement pour les icônes/le manifest.
 */

const CACHE_VERSION = "chantier-shell-v1";
const SHELL_ASSETS = [
  "./app/static/manifest.json",
  "./app/static/icons/icon-192.png",
  "./app/static/icons/icon-512.png",
  "./app/static/icons/apple-touch-icon.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION).then((cache) => cache.addAll(SHELL_ASSETS)).catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((noms) =>
      Promise.all(noms.filter((n) => n !== CACHE_VERSION).map((n) => caches.delete(n)))
    )
  );
  self.clients.claim();
});

const PAGE_HORS_LIGNE = `<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Hors connexion — Suivi de Chantier</title>
<style>
  body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
       background:#0b0c11;color:#f5f5f7;font-family:system-ui,-apple-system,sans-serif;text-align:center;padding:2rem;}
  .box{max-width:360px;}
  .icon{font-size:2.5rem;margin-bottom:1rem;}
  h1{font-size:1.2rem;margin:0 0 .5rem;}
  p{color:#a3a7b7;font-size:.95rem;line-height:1.4;}
  button{margin-top:1.5rem;background:#eab308;color:#171200;border:none;border-radius:11px;
         padding:.7rem 1.4rem;font-weight:700;font-size:.95rem;}
</style></head>
<body><div class="box">
  <div class="icon">📡</div>
  <h1>Pas de connexion</h1>
  <p>Le Suivi de Chantier a besoin d'une connexion pour fonctionner (les données restent en sécurité sur le serveur). Reconnectez-vous puis réessayez.</p>
  <button onclick="location.reload()">Réessayer</button>
</div></body></html>`;

self.addEventListener("fetch", (event) => {
  const { request } = event;

  // Pages/documents : toujours privilégier le réseau (données à jour),
  // repli sur l'écran "hors connexion" seulement si le réseau échoue.
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(
        () => new Response(PAGE_HORS_LIGNE, { headers: { "Content-Type": "text/html; charset=utf-8" } })
      )
    );
    return;
  }

  // Icônes/manifest de la coquille : cache d'abord, réseau en repli.
  if (SHELL_ASSETS.some((asset) => request.url.endsWith(asset.replace("./", "")))) {
    event.respondWith(
      caches.match(request).then((cached) => cached || fetch(request))
    );
  }
});

// ---------------------------------------------------------------------------
// Notifications push — architecture prête, non activée (pas d'envoi serveur
// tant que utils/notifications.py n'implémente pas l'envoi VAPID/pywebpush).
// ---------------------------------------------------------------------------
self.addEventListener("push", (event) => {
  if (!event.data) return;
  let payload = {};
  try {
    payload = event.data.json();
  } catch (e) {
    payload = { title: "Suivi de Chantier", body: event.data.text() };
  }
  event.waitUntil(
    self.registration.showNotification(payload.title || "Suivi de Chantier", {
      body: payload.body || "",
      icon: "./app/static/icons/icon-192.png",
      badge: "./app/static/icons/icon-192.png",
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(
    clients.matchAll({ type: "window" }).then((liste) => {
      if (liste.length > 0) return liste[0].focus();
      return clients.openWindow("./");
    })
  );
});
