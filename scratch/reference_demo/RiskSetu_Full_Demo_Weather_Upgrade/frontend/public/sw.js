const CACHE='risksetu-shell-v2';
self.addEventListener('install',event=>{event.waitUntil((async()=>{
 const cache=await caches.open(CACHE);const shell=await fetch('/');if(!shell.ok)throw new Error('App shell unavailable');
 const html=await shell.clone().text();await cache.put('/',shell);
 const assets=[...html.matchAll(/(?:src|href)="(\/assets\/[^"\s]+)"/g)].map(m=>m[1]);
 await cache.addAll(['/icon.svg','/manifest.webmanifest',...new Set(assets)]);
 await self.skipWaiting();
})())});
self.addEventListener('activate',event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)))));self.clients.claim()});
self.addEventListener('fetch',event=>{
 const url=new URL(event.request.url);
 // Never cache private APIs, credentials, media, or map-provider tiles.
 if(event.request.method!=='GET'||url.origin!==self.location.origin||url.pathname.startsWith('/api')||url.pathname.startsWith('/@'))return;
 if(event.request.mode==='navigate'){
  event.respondWith(fetch(event.request).then(r=>{if(r.ok){const copy=r.clone();caches.open(CACHE).then(c=>c.put('/',copy))}return r}).catch(()=>caches.match('/')));return;
 }
 if(url.pathname.startsWith('/assets/')||url.pathname==='/icon.svg')event.respondWith(caches.match(event.request).then(cached=>cached||fetch(event.request).then(r=>{if(r.ok){const copy=r.clone();caches.open(CACHE).then(c=>c.put(event.request,copy))}return r})));
});
self.addEventListener('push',event=>{const data=event.data?.json()||{};event.waitUntil(self.registration.showNotification(data.title||'RiskSetu',{body:data.message||'Open RiskSetu for current information.',icon:'/icon.svg',data:{url:'/'}}))});
self.addEventListener('notificationclick',event=>{event.notification.close();event.waitUntil(self.clients.openWindow('/'))});
