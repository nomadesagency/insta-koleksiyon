---
name: insta-koleksiyon
description: >
  Instagram "Kaydedilenler" listesindeki postların açıklamasını, görsel üstü metin dökümünü (altyazı değil)
  ve varsa konuşma transkriptini toplar, sabit taksonomiyle kategorileyip tek Excel'e yazar. Tarayıcı aracı
  olan bir ajanla çalışır (Instagram'a giriş yapılmış Chrome oturumu gerekir).
---

# insta-koleksiyon

Bu klasörde kişisel veri TUTULMAZ. Küçük dosyalar (`state.json`, `config.json`, Excel) `--workdir` ile verilen özel çalışma alanındadır. **Ağır dosyalar (`media/`, `frames/`) çalışma alanına girmez:** `--cachedir` ile ayrı yerde tutulur (varsayılan `~/Desktop/insta-koleksiyon-cache`, `config.json` → `cache_dir` ile değiştirilir). Cachedir çalışma alanının içinde olamaz; betik reddeder. Böylece çalışma alanı bir bulut klasöründeyse senkron yükü küçük kalır. Bu klasör olduğu gibi paylaşılabilir kalmalıdır: kullanıcı adı, yol, token, e-posta yazılmaz.

## Kapsam kuralları
- "Transkript" = görsel üstü metin dökümü. **Yanık altyazı (konuşmayı kelime kelime yazan metin) dahil edilmez.** Konuşma varsa ses transkripti AYRI sütundadır.
- **Ayrım kuralı:** tasarlanmış ekran metni (başlık, sahne başlığı, diyagram etiketi, vurgulu cümle) dahil; konuşmayı senkron yazan 1-4 kelimelik altyazı hariç. Müzik eşliğinde yalnız söz/metinden oluşan videoda (şarkı sözü yazısı) söz metni dahil.
- **Medya yeri ve temizlik:** indirilen video/görsel/kareler önbellek klasörüne yazılır; kalıcı çıktı yalnız `state.json` + Excel'dir. Başarılı her turdan sonra önbellek **silinir** (`ig_finish_batch.py`). Medya kalıcı arşiv değildir: gerekirse post URL'sinden bakılır.
- Önce pilot (son 10-20 post), sonuç beğenilince tam koşu.
- Metin: toplu OCR + şüpheli olanları inceleyen (sen ya da ajan) görsel okuyup düzeltir (karma). Resimli postlarda doğrudan görsel okuma.
- Kategori: yalnız postun kendi içeriğinden, sabit taksonomiyle. Serbest etiket üretilmez.

## Ön koşullar
- `brew install ffmpeg yt-dlp tesseract tesseract-lang` · `python3 -m pip install --user openpyxl pillow faster-whisper`
- `python3` = bu paketlerin kurulu olduğu yorumlayıcı. Birden çok Python varsa (ör. sistem Python'u ve Homebrew Python'u) paketlerin hangisine kurulduğunu kontrol et.
- `yt-dlp --cookies-from-browser chrome` ilk çalışmada macOS Anahtar Zinciri izni ister: **Allow** (tek seferlik) yeterli, "Always Allow" önerilmez. İzin pencerelerini kullanıcı onaylar, ajan şifre girmez.
- Chrome'da Instagram'a giriş açık olmalı.

## Hızlı yol (önerilen: parti başına ≈ 7 dk makine + inceleme)
Kısaltma: `S=<bu klasör>/scripts`, `W=<özel çalışma alanın>`, `C=~/Desktop/insta-koleksiyon-cache`. Chrome parçacıkları: `chrome-snippets.md`.
1. **Döküm (Chrome, tek sefer ya da süresi dolunca):** `chrome-snippets.md` parça 1 (ilk N sayfa yeter) → parça 2 ile panoya → `pbpaste > $C/saved-feed.json`. Dökümde reel video adresleri, carousel/foto görselleri, açıklama, hesap, tarih, ses türü hazırdır; adresler **birkaç saatte** dolar.
2. **Parti (tek komut):** `python3 $S/ig_run_batch.py --workdir $W --feed $C/saved-feed.json --new 50` → yeni 50 postu ekler, medyayı **paralel** indirir (yt-dlp/çerez/Anahtar Zinciri yok), kareleri paralel çıkarır, **OCR ve Whisper aynı anda** koşar, altyazıyı ayıklar, süreleri ve bekleyen sayısını yazar. Yarıda kalırsa aynı komut devam eder.
3. **İnceleme (atlanamaz):** `python3 $S/ig_board.py --workdir $W --pending` bekleyen TÜM postların (işaretli + OTO) panolarını ve metin özetini tek seferde üretir. Panoları paralel oku, sonuçları `python3 $S/ig_apply.py --workdir $W < sonuc.json` ile yaz (kategori harf kodu A..M: `ig_apply.py --letters`). `[ŞÜPHELİ: şarkı sözü olabilir]` etiketi: panoda konuşan yüz yoksa `has_speech:false` yaz.
4. **Turu bitir + temizle (tek komut):** `python3 $S/ig_finish_batch.py --workdir $W`. Sırasıyla Excel'i üretir, state ile hücre hücre doğrular (`verify_xlsx.py`), **yalnız başarılıysa** önbellekteki `media/` + `frames/` klasörlerini siler. Şu durumlarda **hiçbir şey silinmez**: `done` olmayan post var, Excel state ile tutmuyor, kategori taksonomide yok. Bir sonraki turdan önce önbellek boş olmalıdır.

Ölçülen süreler (30 gerçek post, 10 çekirdek): eski hat 524 sn → yeni hat 226 sn (medya 42, kareler 11, OCR‖konuşma 173). Kalan tek büyük kalem **görsel inceleme**: aşağıdaki "Hız notları".

## Hız notları
- **OCR 237 → 96 sn:** 720×1280 video karesi 2 kat büyütülmez (`IG_OCR_UPSCALE_BELOW`, 600) ve ters renk geçişi yalnız düz okuma zayıfsa (satır ort. güveni < 80) denenir. Kalite aynı kaldı.
- **Whisper 363 → 148 sn:** `beam_size=1`, 3 süreç × az iş parçacığı (`speech_workers`), `condition_on_previous_text=False`. Transkript benzerliği medyan 0,93 (farklar yazım: "150.000"/"150 bin").
- **Uzun videoda yarım kare sıklığı:** `long_video_seconds` (45) üstü videolarda `frame_fps_long` (0,5).
- **state yazımı kilitli ve birleştirmeli:** iki betik ya da elle yazım aynı anda güvenle çalışır. Binlerce postluk state'te şişmemesi için `ig_cleanup` biten postların `frames/sheet/media` yollarını da siler.
- **Hala yavaş olan:** görsel inceleme (50 post ≈ 50 pano okuma). Standart: işaretli + otomatik geçen HEPSİ okunur (bir denemede otomatik geçen 12 postun 12'sinde de ekran metni eksik/yanlış çıktı). Zamanı kısaltmak için panoları 10-12'şer paralel oku, sonuçları tek `ig_apply` çağrısında yaz.

## Akış (ayrıntılı, adım adım; hızlı yol bunların birleşimidir)
`media/` ve `frames/` okuyan/yazan betikler (`ig_download`, `ig_fetch_images`, `ig_frames`, `ig_ocr`, `ig_speech`, `ig_board`, `ig_cleanup`) önbellek klasörünü kendileri çözer; elle `--cachedir` yalnız varsayılandan farklı yer için gerekir.

1. **Liste (Chrome).** Yeni sekmede `instagram.com/<kullanıcı>/saved/all-posts/` (`/saved/` yalnız koleksiyonları gösterir). Tarayıcı aracıyla `a[href*="/p/"]` hrefleri sırayla topla (Instagram sırası = kaydedilme sırası, en yeni önce). Kaydırmadan yalnız ilk ~21 kart DOM'dadır; tam liste için kaydır. Tür ipucu: kartın `svg[aria-label]` değeri (`Clip`=reel, `Carousel`, boş=foto). `$W/urls.json`'a yaz → `python3 $S/ig_state.py --workdir $W add-list --file $W/urls.json --limit N`
2. **Video postlar (yedek yol).** Hızlı yolda `ig_import_feed.py` doğrudan adresten indirir; adresi olmayan/süresi dolan reel için `python3 $S/ig_download.py --workdir $W` (yt-dlp: video + `.info.json`; açıklama, hesap=`channel`, tarih, süre otomatik state'e yazılır. `uploader_id` sayısal ID'dir, kullanılmaz). Resimli postta yt-dlp hata verir (beklenen).
3. **Resimli postlar (carousel/foto): meta.** Sayfa içinden `fetch('/p/<kod>/',{credentials:'include'})` + `og:description`. Biçim değişkendir (`N likes… - hesap on TARİH: "açıklama"` / yalnız açıklama / açıklamasız); bulunamazsa yt-dlp yolu (videolarda) kullanılır. Toplu fetch tarayıcı aracının zaman sınırını aşabilir: işi `window.__x` içinde başlat, sonra yokla.
   **3b. Resimli postlar: içerik.** Sayfada her slaytı gezip (`button[aria-label="Next"]` tıklaması) görünür büyük `img` URL'lerini topla. Taşıma, öncelik sırasıyla: (a) **Pano yolu (önerilen, izin gerektirmez):** sayfaya bir düğme enjekte et (`position:fixed`), onclick'inde `navigator.clipboard.writeText(JSON)`; düğmeye **gerçek fare tıklaması** yap (JS `click()` pano/indirme için "kullanıcı hareketi" sayılmaz). Sonra terminalde `LANG=en_US.UTF-8 pbpaste > ~/Downloads/ig_images_<kod>.json` (UTF-8 yerel ayarı şart; yoksa Türkçe/emoji bozulur). (b) Blob indirmesi: Chrome'da instagram.com için "otomatik indirme" izni verilmişse çalışır, ama pratikte yalnız ilk dosyayı indirip sonrasını sessizce engelleyebilir. JSON: `{code, handle, date_text, caption, urls[]}`. Sonra `python3 $S/ig_fetch_images.py --workdir $W` (görselleri `media/<kod>/NN.jpg` yapar, açıklama/hesap/tarihi state'e yazar). Tarayıcı aracının çıktısı sorgu parametreli URL'leri gizleyebilir; bu normaldir, atlatılmaz. Uzun carousel'lerde slayt sayısını sayfadan doğrula.
4. **Kareler.** `python3 $S/ig_frames.py --workdir $W` (1 fps, benzer kare eleme, en çok `max_frames`, kontak sayfası `frames/<kod>/_sheet.jpg` = süreyi kapsayan 12 kare).
5. **OCR.** `python3 $S/ig_ocr.py --workdir $W`. Gürültü süzgeci: satır güveni + harf oranı + (kare>6 ise) satırın ≥2 karede görünmesi. Karışık zeminli videoda (kumaş, doğa) ham OCR yüzlerce çöp satır üretir; süzgeç bunu keser. **Stilize/dış çizgili başlıklar OCR'dan kaçar: adım 7 bu yüzden zorunlu.**
6. **Konuşma.** `python3 $S/ig_speech.py --workdir $W` (ses var mı + Whisper; müzik-only = konuşma yok; ilk çalıştırmada model iner). Ardından `python3 $S/ig_subtitles.py --workdir $W`: konuşmayla örtüşen KISA OCR satırlarını altyazı sayıp ayıklar; satır atılan post `GÖZDEN GEÇİR` olur (3-4 kelimelik sahne başlıkları yanlış ayıklanabilir).
7. **Gözden geçirme (atlanamaz).** `python3 $S/ig_board.py --workdir $W --batch 0 --size 6` her partide 6 postun inceleme panosunu (`frames/<kod>/_board.jpg`: ilk 2 kare + eşit aralıklı 6 kare; carousel/foto için `_slides_N.jpg`, 6 slayt/sayfa) üretir ve OCR/altyazı/konuşma özetini basar. Panoları görsel oku, sonucu `ig_state.py set` ile yaz (`screen_text`, `text_status: DÜZELTİLDİ`, `note`). Bir sonraki partide kalan sayı azalır (düzeltilen post listeden çıkar). **"OTO" geçen postlar da okunur:** stilize başlıklar yüksek OCR puanıyla bile kaçabilir ya da yarım okunabilir. Carousel/foto postlarında OCR zayıftır: hepsi görsel okunur. Görsel olarak doğrulanamayan post `GÖZDEN GEÇİR` kalır; Excel'in Hata-Eksik sayfasında görünür.
8. **Kategorileme.** Açıklama + `screen_text` + `speech_text`. Taksonomi: `$W/taxonomy.json`, yoksa `taxonomy.default.json`. 1 ana kategori + en fazla 2 ikincil etiket; liste dışı değer yazılmaz, uymuyorsa `Diğer` + `note`. `ig_state.py set --code X --json '{"category":"..","tags":[".."],"_stage":"done"}'`
9. **Excel.** `python3 $S/build_xlsx.py --workdir $W` → `$W/kaydedilenler.xlsx` (Kaydedilenler · Hata-Eksik · Kategori Dağılımı). Liste dışı kategori = dosya üretilmez.
10. **Temizlik.** Elle yapılacaksa `ig_cleanup.py --apply`; hızlı yolda `ig_finish_batch.py` bunu doğrulamadan sonra kendisi çalıştırır. Silinen post `media_purged: true` alır, `frames/sheet/media` yolları state'ten de düşer; `ig_download` yeniden indirmez. Excel + `state.json` + URL yeterlidir.

## Kalite kapıları
- Excel satır sayısı = state.json post sayısı; Excel hücreleri state ile birebir karşılaştırılır.
- "Diğer" oranı %15'i geçerse taksonomiyi gözden geçir; kategori eklendikten sonra eski postlar yeniden kategorilenir.
- Konuşmalı reel, yalnız metinli reel, carousel için en az birer örnek elle karşılaştırılır.

## Operasyon dersleri
- **Paralel yazım:** `save_state` kilitli ve birleştirmelidir, ama bir zincir çalışırken state'e elle yazarsan zincirin bellekteki kopyası o alanı tekrar yazabilir. Önce zincirin bitmesini bekle ya da yazdıktan sonra alanı doğrula.
- **Arka plan işi çıktısı tamponlanır:** log boş görünse de ilerleme `state.json`'dadır; sayımla izle.
- **Boyut:** 100 post ≈ 1,4 GB medya + 1,1 GB kare (5000 post ≈ 70 GB). Bu yüzden önbellek çalışma alanı dışındadır ve her tur sonunda `ig_finish_batch.py` ile temizlenir.
- **Konuşma:** `ig_speech.py` medyası olmayan postu "konuşma yok" yazar; medya sonradan gelirse `speech_text`/`has_speech` alanlarını silip yeniden çalıştır.
- **Şarkı sözü = konuşma değil:** Whisper arka plandaki şarkı sözünü konuşma sayabilir. İnceleme panosunda `KONUŞMA` satırı şarkı sözü gibi akıyorsa ve videoda konuşan yüz yoksa `has_speech: false`, `speech_text: ""` yaz. Lisanslı müzik etiketi tek başına eleme sebebi değildir: müzik üstüne gerçek seslendirme yapılan postlar da var.
- **Bekleme döngüsünde `pgrep -f`:** döngünün kendi komut satırı deseni yakalar ve hiç bitmez; deseni `'scripts/ig_[a-z]+\.py'` gibi kendi metnini eşleştirmeyen biçimde yaz.
- **Koleksiyonlar:** akış API'sindeki `saved_collection_ids` üyelerin hepsini göstermez. Üyelik için `/api/v1/feed/collection/<id>/posts/` okunur (`chrome-snippets.md` parça 3). **Kaydetme tarihi Instagram'ın web verisinde yoktur** (yalnız paylaşım tarihi `taken_at`); gerçek tarih için hesap verisi dışa aktarımı (Hesap Merkezi) gerekir.
- **Toplu liste ve meta:** `/api/v1/feed/saved/posts/` sayfalama ile (sayfa başına ~20 post, ~1 sn arayla) tüm kaydedilenlerin açıklama, hesap, tarih (`taken_at`), tür ve carousel/foto görsel adreslerini tek taramada verir. Sonuç panoya → `saved-feed.json` (önbelleğe koy) → `ig_import_feed.py` medyayı indirir (adresler imzalıdır ve süresi dolar; indirmeden hemen önce taze döküm al). Dökümde `media_type` 1 foto, 2 video, 8 carousel.
- **Yeni post ekleme:** `ig_state.py add-list --append-new --limit N` yalnız state'te olmayan kodları ekler, sırayı mevcut en büyük order'dan sürdürür, mevcut hiçbir order'ı değiştirmez. Eski `add-list` (bayraksız) listeye göre order'ı **yeniden yazar**: kısmi listeyle çalıştırma.
- **Carousel'de yt-dlp:** bazı carousel'ler (video slaytlı) yt-dlp'de "No video formats found" verir; bunlar `ig_import_feed.py` yoluyla alınır. Videolu carousel'in kare/OCR adımları yine çalışır.
- **Doğrulama betiği:** Excel `Sıra` sütunu metin yazılır (`clean()` hepsini str yapar); state ile karşılaştırırken tipi eşitle.

## Sınırlar
- Instagram hesabına otomasyon riski: bekleme süresini kısaltma, partileri küçük tut, hesap uyarısı görülürse dur.
- OCR stilize fontta ve karışık zeminde zayıf; güven puanı tek başına güvenilir değildir (eksik okunan satır yüksek puan alabilir).
- Whisper kısa/gürültülü seste hata yapar; konuşma tespiti `audio_min_mean_volume_db` eşiğine bağlıdır.
- Medya, kareler ve çalışma alanı kişisel veridir; hiçbir public adrese gitmez, repoya eklenmez.
