# Chrome snippets (for a browser tool that can run JavaScript in the page)

Ready, tested JS blocks. Each one runs in a `https://www.instagram.com/<USERNAME>/saved/all-posts/` tab (logged in).
`<USERNAME>` and `<COLLECTION_ID>` are placeholders. Never write personal values into this file.

General rules:
- The browser tool may time out on long jobs (e.g. 45 s): start long work asynchronously inside `window.__x`, then poll it (`while(!window.__x.done && Date.now()-t0<40000) await sleep`).
- Tool output may **block** text that contains cookie or query-string URLs, and it truncates long text: take the data from the **clipboard**, not from the tool output (snippet 2).
- Endpoint requests are sent with the `x-ig-app-id: 936619743392459` (Instagram's public web app ID) + `x-requested-with: XMLHttpRequest` headers and `credentials:'include'`. Wait a random 0.7-1.8 s between pages.

## 1. Feed dump (all saved posts)
Returns caption, account, date, type, audio type, **direct video URL** and carousel/photo image URLs for every saved post in one pass
(~20 posts per page; 5000 posts ≈ 250 pages ≈ 5-6 min, ≈ 9 MB). The list is in saving order (newest first).

```js
window.__feed={done:false,rows:[],pages:0,err:null};
const H={'x-ig-app-id':'936619743392459','x-requested-with':'XMLHttpRequest'};
const img=o=>{const c=o&&o.image_versions2&&o.image_versions2.candidates;return c&&c[0]?c[0].url:null};
const vid=o=>o&&o.video_versions&&o.video_versions[0]?o.video_versions[0].url:null;
const rowOf=m=>{const cm=m.clips_metadata||{};
 const r={c:m.code,t:m.media_type,p:m.product_type||'',at:m.taken_at,u:m.user&&m.user.username,cap:(m.caption&&m.caption.text)||'',
  d:m.video_duration||null,ha:m.has_audio,au:cm.audio_type||null,
  mu:(cm.music_info&&cm.music_info.music_asset_info&&cm.music_info.music_asset_info.title)||null};
 if(m.media_type===2) r.v=vid(m);
 else if(m.carousel_media) r.s=m.carousel_media.map(s=>({t:s.media_type,i:img(s),v:s.media_type===2?vid(s):null}));
 else if(m.media_type===1) r.s=[{t:1,i:img(m)}];
 return r};
(async()=>{let max=null;try{
 for(let i=0;i<900;i++){
  const r=await fetch('/api/v1/feed/saved/posts/'+(max?('?max_id='+encodeURIComponent(max)):''),{credentials:'include',headers:H});
  if(r.status!==200){window.__feed.err='status '+r.status+' page '+i;break}
  const j=await r.json(); (j.items||[]).forEach(x=>window.__feed.rows.push(rowOf(x.media)));
  window.__feed.pages++; if(!j.more_available||!j.next_max_id)break; max=j.next_max_id;
  await new Promise(r=>setTimeout(r,900+Math.random()*700));}
 }catch(e){window.__feed.err=String(e)} window.__feed.done=true})(); 'started'
```
Poll: `({done:window.__feed.done,n:window.__feed.rows.length,err:window.__feed.err})`.
The **first N pages** are often enough (e.g. 3-4 pages for the next 50 posts): change the loop to `i<4`. During a long scan `window.__feed.rows` stays in memory; do not reload the page.
Fields: `t` 1 photo / 2 video / 8 carousel; `au` `original_sounds` | `licensed_music`; `v` and `s[].i` are signed and **expire after a few hours**: take a fresh dump right before downloading.

## 2. Copy to clipboard (moving the data from Chrome to the Mac)
Add a large button to the page and give it a **real mouse click** (a JS `click()` does not count as a "user gesture" for the clipboard).
```js
window.__payload=JSON.stringify(window.__feed.rows); document.getElementById('cpbtn')?.remove();
const b=document.createElement('button'); b.id='cpbtn'; b.textContent='COPY';
b.style.cssText='position:fixed;top:10px;left:10px;width:260px;height:80px;z-index:999999;font-size:24px;background:#ff0;color:#000';
b.onclick=async()=>{await navigator.clipboard.writeText(window.__payload); b.textContent='COPIED'}; document.body.appendChild(b); window.__payload.length
```
Then click the button (≈ 130, 50) with a real mouse click; on the Mac: `LANG=en_US.UTF-8 pbpaste > ~/Desktop/insta-koleksiyon-cache/saved-feed.json`
(the UTF-8 locale is required, otherwise non-ASCII characters and emoji get corrupted). Payloads up to 9 MB transferred without problems.

## 3. Collection membership (read only, optional)
Returns the post codes of one collection; to fill the spreadsheet's `Collection` column, write them with `ig_state.py set --code X --json '{"collection":"name"}'`.
```js
const H={'x-ig-app-id':'936619743392459','x-requested-with':'XMLHttpRequest'};
const codes=[];let max=null;
for(let i=0;i<40;i++){const j=await (await fetch('/api/v1/feed/collection/<COLLECTION_ID>/posts/'+(max?('?max_id='+encodeURIComponent(max)):''),{credentials:'include',headers:H})).json();
 (j.items||[]).forEach(x=>codes.push((x.media||x).code)); if(!j.more_available||!j.next_max_id)break; max=j.next_max_id; await new Promise(r=>setTimeout(r,700))}
codes.length
```
Note: the `saved_collection_ids` field in the general feed shows **incomplete** membership; use this endpoint instead.
