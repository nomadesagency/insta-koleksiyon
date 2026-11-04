# Chrome parçacıkları (tarayıcı aracının JavaScript çalıştırma özelliği)

Hazır, denenmiş JS blokları. Her biri `https://www.instagram.com/<KULLANICI>/saved/all-posts/` sekmesinde çalışır (giriş açık).
`<KULLANICI>`, `<KOLEKSIYON_ID>` yer tutucudur. Bu dosyaya özel değer yazılmaz.

Genel kurallar:
- Tarayıcı aracı uzun işte zaman aşımına uğrayabilir (ör. 45 sn): uzun işi `window.__x` içinde asenkron başlat, sonra yokla (`while(!window.__x.done && Date.now()-t0<40000) await sleep`).
- Araç çıktısı çerez/sorgu parametreli URL içeren metni **engeller** ve uzun metni keser: veriyi çıktıdan değil **panodan** al (parça 2).
- Uç istekleri `x-ig-app-id: 936619743392459` + `x-requested-with: XMLHttpRequest` başlıklarıyla, `credentials:'include'` ile yapılır. Sayfalar arası 0,7-1,8 sn rastgele bekle.

## 1. Besleme dökümü (tüm kaydedilenler)
Tüm kaydedilenlerin açıklama, hesap, tarih, tür, ses türü, **doğrudan video adresi** ve carousel/foto görsel adreslerini tek taramada verir
(sayfa başına ~20 post; 5000 post ≈ 250 sayfa ≈ 5-6 dk, ≈ 9 MB). Sayfa listesi kaydedilme sırasındadır (en yeni önce).

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
  if(r.status!==200){window.__feed.err='status '+r.status+' sayfa '+i;break}
  const j=await r.json(); (j.items||[]).forEach(x=>window.__feed.rows.push(rowOf(x.media)));
  window.__feed.pages++; if(!j.more_available||!j.next_max_id)break; max=j.next_max_id;
  await new Promise(r=>setTimeout(r,900+Math.random()*700));}
 }catch(e){window.__feed.err=String(e)} window.__feed.done=true})(); 'başladı'
```
Yoklama: `({done:window.__feed.done,n:window.__feed.rows.length,err:window.__feed.err})`.
Yalnız **ilk N sayfa** yeter (ör. sıradaki 50 post için 3-4 sayfa): döngüyü `i<4` yap. Uzun taramada `window.__feed.rows` bellekte kalır, sayfayı yenileme.
Alanlar: `t` 1 foto / 2 video / 8 carousel; `au` `original_sounds` | `licensed_music`; `v` ve `s[].i` imzalıdır, **birkaç saat sonra süresi dolar**: indirmeden önce taze döküm al.

## 2. Panoya kopyalama (veriyi Chrome'dan Mac'e taşıma)
Sayfaya büyük bir düğme ekle, **gerçek fare tıklaması** yap (JS `click()` pano için "kullanıcı hareketi" sayılmaz).
```js
window.__payload=JSON.stringify(window.__feed.rows); document.getElementById('cpbtn')?.remove();
const b=document.createElement('button'); b.id='cpbtn'; b.textContent='KOPYALA';
b.style.cssText='position:fixed;top:10px;left:10px;width:260px;height:80px;z-index:999999;font-size:24px;background:#ff0;color:#000';
b.onclick=async()=>{await navigator.clipboard.writeText(window.__payload); b.textContent='KOPYALANDI'}; document.body.appendChild(b); window.__payload.length
```
Sonra düğmeye (≈ 130, 50) gerçek fare tıklaması yap; Mac'te: `LANG=en_US.UTF-8 pbpaste > ~/Desktop/insta-koleksiyon-cache/saved-feed.json`
(UTF-8 yerel ayarı şart: yoksa Türkçe/emoji bozulur). 9 MB'a kadar sorunsuz taşındı.

## 3. Koleksiyon üyeliği (okuma, isteğe bağlı)
Bir koleksiyonun post kodlarını verir; Excel'in `Koleksiyon` sütununu doldurmak için `ig_state.py set --code X --json '{"collection":"ad"}'` ile yazılır.
```js
const H={'x-ig-app-id':'936619743392459','x-requested-with':'XMLHttpRequest'};
const codes=[];let max=null;
for(let i=0;i<40;i++){const j=await (await fetch('/api/v1/feed/collection/<KOLEKSIYON_ID>/posts/'+(max?('?max_id='+encodeURIComponent(max)):''),{credentials:'include',headers:H})).json();
 (j.items||[]).forEach(x=>codes.push((x.media||x).code)); if(!j.more_available||!j.next_max_id)break; max=j.next_max_id; await new Promise(r=>setTimeout(r,700))}
codes.length
```
Not: genel akıştaki `saved_collection_ids` üyeleri **eksik** gösterir; üyelik için bu uç kullanılır.
