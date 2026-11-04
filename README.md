# insta-koleksiyon

[Türkçe](#türkçe) · [English](#english)

---

## Türkçe

Instagram'da "Kaydedilenler"e attığın postlar bir süre sonra kaybolup gider. insta-koleksiyon bu listeyi aranabilir bir Excel'e çevirir. Her post için şunlar çıkar:

- post açıklaması, hesap, tür, yayın tarihi ve URL
- görsel üstü metin (OCR + görsel inceleme; yanık altyazı hariç)
- konuşma varsa ses transkripti (Whisper)
- sabit bir taksonomiden otomatik kategori ve en fazla 2 etiket

Araç, tarayıcı kontrolü olan bir yapay zeka ajanıyla (ör. Claude Code + Claude in Chrome) çalışmak üzere tasarlandı. Kaydedilenler listesi özeldir, bu yüzden giriş yapılmış bir Chrome oturumu gerekir. Akışın tamamı [SKILL.md](SKILL.md) dosyasında. Bu README dışındaki tüm dosyalar (belgeler, betik mesajları, Excel sütunları, kategoriler) İngilizcedir.

### Gereksinimler
- macOS, Python 3.9+
- `python3 -m pip install --user openpyxl pillow faster-whisper`
- `brew install ffmpeg yt-dlp tesseract tesseract-lang`
- Instagram'a giriş yapılmış Chrome ve tarayıcı aracı olan bir ajan

### Kurulum
1. Özel bir çalışma klasörü aç (repo dışında). Bu klasörde kullanıcı adın, kaydettiğin postların listesi ve Excel durur. **Asla repoya ekleme.**
2. `config.example.json` dosyasını `<çalışma-klasörü>/config.json` olarak kopyala, `instagram_username` alanını doldur.
3. İstersen `taxonomy.default.json` dosyasını `<çalışma-klasörü>/taxonomy.json` olarak kopyalayıp kategorileri kendine göre düzenle. Varsayılan kategoriler (İngilizce) içerik üreticileri için hazırlanmış bir örnektir; Türkçe kategori adları da yazabilirsin.
4. Aracın ürettiği tüm dosyalar bu çalışma klasörüne yazılır: `saved-posts.xlsx`, `state.json`, döküm (`saved-feed.json`) ve diğer JSON'lar, geçici `media/` ve `frames/` klasörleri (her parti sonunda silinir). Klasör buluttaysa ağır medyayı ayırmak için `config.json` içinde `cache_dir` alanını kullan ya da `--cachedir` ver (100 post ≈ 2,5 GB geçici).
5. OCR dilleri `config.json` → `ocr_languages` (varsayılan `tur+eng`, tesseract dil kodları).

### Hızlı yol
```bash
S=scripts; W=~/insta-koleksiyon-veri
# 1) chrome-snippets.md parça 1 + 2 ile kaydedilenler dökümünü al:  pbpaste > $W/saved-feed.json
python3 $S/ig_run_batch.py   --workdir $W --new 50                             # indirme, kareler, OCR, konuşma
python3 $S/ig_board.py       --workdir $W --pending                            # inceleme panoları
python3 $S/ig_apply.py       --workdir $W < results.json                       # inceleme sonuçları + kategori
python3 $S/ig_finish_batch.py --workdir $W                                     # Excel + doğrulama + medya temizliği
```
50 postluk bir parti, 10 çekirdekli bir makinede yaklaşık 7 dakikada hazırlanır. En uzun adım görsel incelemedir.

### Notlar
- Betikler idempotenttir: tekrar çalıştırınca biten postlar atlanır.
- `build_xlsx.py`, taksonomide olmayan bir kategori görürse Excel'i yazmaz.
- `ig_finish_batch.py` geçici medyayı yalnız Excel state ile birebir tuttuğunda siler.
- Bir Instagram hesabını otomatikleştirmek hız sınırı ya da uyarı riski taşır. Bekleme sürelerini kısaltma, partileri küçük tut.
- Bu proje Instagram ya da Meta ile bağlantılı değildir. Kendi hesabının verisini kendi bilgisayarında işlemek içindir.

---

## English

Posts you save on Instagram tend to disappear into the "Saved" list. insta-koleksiyon turns that list into a searchable spreadsheet. For every post you get:

- caption, account, type, publish date and URL
- on-screen text (OCR plus visual review; burned-in subtitles excluded)
- a speech transcript when there is speech (Whisper)
- an automatic category from a fixed taxonomy, plus up to 2 tags

It is built to be driven by an AI agent with browser control (for example Claude Code with Claude in Chrome). The Saved list is private, so a logged-in Chrome session is required. The full workflow is in [SKILL.md](SKILL.md).

### Requirements
- macOS, Python 3.9+
- `python3 -m pip install --user openpyxl pillow faster-whisper`
- `brew install ffmpeg yt-dlp tesseract tesseract-lang`
- Chrome logged in to Instagram, and an agent with browser tools

### Setup
1. Create a private working folder outside the repository. It holds your username, the list of your saved posts and the spreadsheet. **Never commit it.**
2. Copy `config.example.json` to `<workdir>/config.json` and set `instagram_username`.
3. Optionally copy `taxonomy.default.json` to `<workdir>/taxonomy.json` and edit the categories. The default categories are an example aimed at content creators.
4. Everything the tool produces is written to this working folder: `saved-posts.xlsx`, `state.json`, the feed dump (`saved-feed.json`) and other JSON files, plus the temporary `media/` and `frames/` folders (deleted after every batch). If the folder is in a cloud drive, move the heavy media elsewhere with `cache_dir` in `config.json` or `--cachedir` (100 posts ≈ 2.5 GB temporarily).
5. OCR languages: `ocr_languages` in `config.json` (default `tur+eng`, tesseract language codes; e.g. `eng` for English only).

### Fast path
```bash
S=scripts; W=~/insta-koleksiyon-data
# 1) dump the Saved feed with chrome-snippets.md parts 1 + 2:  pbpaste > $W/saved-feed.json
python3 $S/ig_run_batch.py   --workdir $W --new 50                             # download, frames, OCR, speech
python3 $S/ig_board.py       --workdir $W --pending                            # review boards
python3 $S/ig_apply.py       --workdir $W < results.json                       # review results + categories
python3 $S/ig_finish_batch.py --workdir $W                                     # spreadsheet + verification + media cleanup
```
A batch of 50 posts is prepared in about 7 minutes on a 10-core machine. The slowest step is the visual review.

### Notes
- Scripts are idempotent: re-running skips finished posts.
- `build_xlsx.py` refuses to write the spreadsheet if a category is not in the taxonomy.
- `ig_finish_batch.py` deletes the temporary media only after the spreadsheet matches the state file cell by cell.
- Automating an Instagram account carries a risk of rate limits or warnings. Keep delays as they are and batches small.
- This project is not affiliated with Instagram or Meta. It is meant for processing your own account's data on your own machine.

## License
MIT. See [LICENSE](LICENSE).
