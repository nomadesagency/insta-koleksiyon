---
name: insta-koleksiyon
description: >
  Collects the caption, the on-screen text (not subtitles) and, when there is speech, the speech transcript of the
  posts in your Instagram "Saved" list, categorises them with a fixed taxonomy and writes everything to one
  spreadsheet. Runs with an agent that has browser tools (needs a Chrome session logged in to Instagram).
---

# insta-koleksiyon

NO personal data is kept in this folder. **Every file the tool reads or writes lives in one place: the private working folder given with `--workdir`** (`config.json`, `state.json`, `urls.json`, `saved-feed.json`, `ig_images_*.json`, `saved-posts.xlsx`, and the temporary `media/` and `frames/` folders). Optional: to keep the heavy `media/` and `frames/` elsewhere (e.g. when the working folder is in a cloud drive; 100 posts ≈ 2.5 GB during a batch), set `cache_dir` in `config.json` or pass `--cachedir`. This folder must stay shareable as it is: no usernames, paths, tokens or e-mail addresses are written into it.

## Scope rules
- "Transcript" = a dump of the text shown on screen. **Burned-in subtitles (text that writes out the speech word by word) are excluded.** When there is speech, the audio transcript goes into a SEPARATE column.
- **Dividing rule:** designed on-screen text (titles, scene titles, diagram labels, highlighted sentences) is included; 1-4 word subtitles synced to speech are excluded. In a video made only of lyrics/text over music, the lyric text is included.
- **Media location and cleanup:** downloaded videos/images/frames are written to `media/` and `frames/` in the working folder; the only permanent output is `state.json` + the spreadsheet. After every successful batch `media/` and `frames/` are **deleted** (`ig_finish_batch.py`). Media is not a permanent archive: when needed, open the post URL.
- Pilot first (the latest 10-20 posts), then the full run once you are happy with the result.
- Text: bulk OCR, then the reviewer (you or an agent) reads the doubtful ones visually and corrects them (hybrid). Image posts are read visually.
- Category: from the post's own content only, using the fixed taxonomy. No free-form tags.

## Prerequisites
- `brew install ffmpeg yt-dlp tesseract tesseract-lang` · `python3 -m pip install --user openpyxl pillow faster-whisper`
- `python3` = the interpreter these packages are installed into. If you have more than one Python (e.g. the system Python and a Homebrew Python), check which one has the packages.
- `yt-dlp --cookies-from-browser chrome` asks for macOS Keychain access on the first run: **Allow** (one time) is enough, "Always Allow" is not recommended. Permission prompts are approved by the user; the agent never types passwords.
- Chrome must be logged in to Instagram.

## Fast path (recommended: ≈ 7 min machine time per batch + review)
Shorthand: `S=<this folder>/scripts`, `W=<your private working folder>`. Chrome snippets: `chrome-snippets.md`.
1. **Dump (Chrome, fresh for every batch):** `chrome-snippets.md` snippet 1 → snippet 2 to the clipboard → `pbpaste > $W/saved-feed.json`. Once the archive exists, make it **incremental**: paste the output of `python3 $S/ig_state.py --workdir $W stop-codes` into the page before snippet 1, and the dump stops as soon as it reaches posts from the previous dump (usually 1-2 pages instead of hundreds; a full scan of thousands of posts can hit Instagram's rate limit). The dump already contains reel video URLs, carousel/photo images, caption, account, date and audio type; the URLs are signed and expire (`ig_import_feed.py` detects expired URLs before downloading and tells you to take a new dump).
2. **Batch (one command):** `python3 $S/ig_run_batch.py --workdir $W --new 50` (reads `$W/saved-feed.json`) → adds the next 50 posts, downloads media **in parallel** (no yt-dlp/cookies/Keychain), extracts frames in parallel, runs **OCR and Whisper at the same time**, strips subtitles, prints durations and the number of posts pending review. If interrupted, the same command resumes.
3. **Review (mandatory):** `python3 $S/ig_board.py --workdir $W --pending` builds the boards and the text summary for ALL pending posts (flagged + AUTO) in one go. Read the boards in parallel and write the results with `python3 $S/ig_apply.py --workdir $W < results.json` (category letter codes A..M: `ig_apply.py --letters`). For big batches, a two-pass review saves time: `--pending --text-only` (summary only, no images) for posts that are clear from caption + OCR + speech, written with `ig_apply.py --mode text`; then `--pending --need-visual` builds boards only for posts that need a look (REVIEW status, carousel/photo, empty OCR), written with the default `--mode visual`. The spreadsheet's **Review** column shows which posts were seen visually and which were decided from text, so text-only posts can be revisited later. `[SUSPECT: may be song lyrics]` label: if nobody is speaking on the board, write `has_speech:false`.
4. **Finish the batch + clean up (one command):** `python3 $S/ig_finish_batch.py --workdir $W`. In order: builds the spreadsheet, compares it with state cell by cell (`verify_xlsx.py`), and **only if that succeeds** deletes the `media/` + `frames/` folders. **Nothing is deleted** when: a post is not `done`, the spreadsheet does not match state, or a category is not in the taxonomy. `media/` and `frames/` should be empty before the next batch.

Measured durations (30 real posts, 10 cores): old pipeline 524 s → new pipeline 226 s (media 42, frames 11, OCR‖speech 173). The only big item left is the **visual review**: see "Speed notes" below.

## Speed notes
- **OCR 237 → 96 s:** 720×1280 video frames are no longer upscaled 2x (`IG_OCR_UPSCALE_BELOW`, 600), and the inverted-colour pass runs only when the plain read is weak (mean line confidence < 80). Quality stayed the same.
- **Whisper 363 → 148 s:** `beam_size=1`, 3 processes × few threads (`speech_workers`), `condition_on_previous_text=False`. Median transcript similarity 0.93 (differences are spelling only, e.g. "150,000"/"150 thousand").
- **Half frame rate for long videos:** above `long_video_seconds` (45), `frame_fps_long` (0.5) is used.
- **State writes are locked and merging:** two scripts, or a script and a hand edit, can write at the same time safely. To keep a state with thousands of posts small, `ig_cleanup` also removes the `frames/sheet/media` paths of finished posts.
- **OCR queue across posts:** the frames of all posts go into one process pool, so photo and small carousel posts (1-3 frames) no longer leave most cores idle. 60 posts / 220 frames: 32.1 s → 5.0 s, identical results.
- **Throttled state saves:** state.json is saved at most every 20 s (`IG_SAVE_EVERY`) and always at exit, instead of after every post. With 5000 posts one save takes ≈0.3 s, so per-post saving cost ≈12 min per 500-post batch.
- **Still slow:** the visual review (50 posts ≈ 50 boards). Standard: flagged + auto-passed posts are ALL read (in one test run, all 12 auto-passed posts had missing or wrong on-screen text). To save time, read the boards 10-12 at a time in parallel and write the results in a single `ig_apply` call.

## Workflow (detailed, step by step; the fast path combines these)
Scripts that read/write `media/` and `frames/` (`ig_download`, `ig_fetch_images`, `ig_frames`, `ig_ocr`, `ig_speech`, `ig_board`, `ig_cleanup`) use the working folder by default; pass `--cachedir` only to put them elsewhere.

1. **List (Chrome).** In a new tab open `instagram.com/<username>/saved/all-posts/` (`/saved/` shows only collections). With the browser tool, collect the `a[href*="/p/"]` hrefs in order (Instagram order = saving order, newest first). Without scrolling only the first ~21 cards are in the DOM; scroll for the full list. Type hint: the card's `svg[aria-label]` value (`Clip`=reel, `Carousel`, empty=photo). Write to `$W/urls.json` → `python3 $S/ig_state.py --workdir $W add-list --file $W/urls.json --limit N`
2. **Video posts (fallback path).** On the fast path `ig_import_feed.py` downloads from the direct URL; for a reel with no URL or an expired one use `python3 $S/ig_download.py --workdir $W` (yt-dlp: video + `.info.json`; caption, account=`channel`, date and duration are written to state automatically. `uploader_id` is a numeric ID and is not used). yt-dlp fails on image posts (expected).
3. **Image posts (carousel/photo): meta.** From inside the page: `fetch('/p/<code>/',{credentials:'include'})` + `og:description`. The format varies (`N likes… - account on DATE: "caption"` / caption only / no caption); if nothing is found, the yt-dlp path is used (for videos). A bulk fetch may exceed the browser tool's time limit: start the job inside `window.__x`, then poll.
   **3b. Image posts: content.** Go through every slide on the page (click `button[aria-label="Next"]`) and collect the visible large `img` URLs. Transfer, in order of preference: (a) **Clipboard path (recommended, needs no permission):** inject a button into the page (`position:fixed`) whose onclick runs `navigator.clipboard.writeText(JSON)`; give the button a **real mouse click** (a JS `click()` does not count as a "user gesture" for the clipboard or downloads). Then in the terminal: `LANG=en_US.UTF-8 pbpaste > $W/ig_images_<code>.json` (the UTF-8 locale is required; otherwise non-ASCII characters and emoji get corrupted). (b) Blob download: works if Chrome has "automatic downloads" permission for instagram.com, but in practice it may download only the first file and silently block the rest; downloaded files land in ~/Downloads, so move them to `$W` or pass `--downloads ~/Downloads`. JSON: `{code, handle, date_text, caption, urls[]}`. Then `python3 $S/ig_fetch_images.py --workdir $W` (saves the images as `media/<code>/NN.jpg` and writes caption/account/date to state). The browser tool's output may hide query-string URLs; that is normal, do not work around it. For long carousels, confirm the slide count on the page.
4. **Frames.** `python3 $S/ig_frames.py --workdir $W` (1 fps, near-duplicate frames dropped, at most `max_frames`, contact sheet `frames/<code>/_sheet.jpg` = 12 frames covering the whole duration).
5. **OCR.** `python3 $S/ig_ocr.py --workdir $W`. Noise filter: line confidence + letter ratio + (if more than 6 frames) the line must appear in ≥2 frames. On videos with busy backgrounds (fabric, nature) raw OCR produces hundreds of junk lines; the filter cuts them. **Stylised/outlined titles escape OCR: that is why step 7 is mandatory.**
6. **Speech.** `python3 $S/ig_speech.py --workdir $W` (is there audio + Whisper; music only = no speech; the model downloads on the first run). Then `python3 $S/ig_subtitles.py --workdir $W`: SHORT OCR lines that overlap the speech are treated as subtitles and removed; a post that loses lines becomes `REVIEW` (3-4 word scene titles can be removed by mistake).
7. **Review (mandatory).** `python3 $S/ig_board.py --workdir $W --batch 0 --size 6` builds the review boards for 6 posts per batch (`frames/<code>/_board.jpg`: first 2 frames + 6 evenly spaced; for carousel/photo `_slides_N.jpg`, 6 slides per page) and prints the OCR/subtitle/speech summary. Read the boards visually and write the result with `ig_state.py set` (`screen_text`, `text_status: CORRECTED`, `note`). The remaining count drops with every batch (corrected posts leave the list). **"AUTO" posts are read too:** stylised titles can be missed or half-read even with a high OCR score. OCR is weak on carousel/photo posts: read all of them visually. A post that cannot be verified visually stays `REVIEW` and shows up on the spreadsheet's Errors-Missing sheet.
8. **Categorising.** Caption + `screen_text` + `speech_text`. Taxonomy: `$W/taxonomy.json`, otherwise `taxonomy.default.json`. 1 main category + at most 2 secondary tags; values outside the list are never written; if nothing fits, use `Other` + `note`. `ig_state.py set --code X --json '{"category":"..","tags":[".."],"_stage":"done"}'`
9. **Spreadsheet.** `python3 $S/build_xlsx.py --workdir $W` → `$W/saved-posts.xlsx` (Saved · Errors-Missing · Category Distribution; the Review column says visual/text). A category outside the list = no file is written.
10. **Cleanup.** By hand: `ig_cleanup.py --apply`; on the fast path `ig_finish_batch.py` runs it after the verification. A deleted post gets `media_purged: true`, its `frames/sheet/media` paths are dropped from state too, and `ig_download` does not download it again. The spreadsheet + `state.json` + URL are enough.

## Quality gates
- Spreadsheet row count = post count in state.json; spreadsheet cells are compared with state one to one.
- If the share of "Other" goes above 15%, review the taxonomy; after adding categories, recategorise the older posts.
- Compare at least one speech reel, one text-only reel and one carousel by hand.

## Lessons from real runs
- **Concurrent writes:** `save_state` is locked and merging, but if you edit state by hand while a chain is running, the chain's in-memory copy can write that field again. Wait for the chain to finish, or check the field after writing.
- **Background job output is buffered:** even if the log looks empty, progress is in `state.json`; track it by counting.
- **Size:** 100 posts ≈ 1.4 GB media + 1.1 GB frames (5000 posts ≈ 70 GB). That is why `media/` and `frames/` are cleaned with `ig_finish_batch.py` after every batch; if the working folder is synced, set `cache_dir` to a local folder.
- **Speech:** `ig_speech.py` records "no speech" for a post without media; if the media arrives later, delete the `speech_text`/`has_speech` fields and run it again.
- **Song lyrics are not speech:** Whisper may treat background lyrics as speech. If the `SPEECH` line on the review board reads like lyrics and nobody is speaking in the video, write `has_speech: false`, `speech_text: ""`. The licensed-music label alone is not a reason to drop speech: some posts have real voice-over on top of music.
- **`pgrep -f` in a wait loop:** it matches the loop's own command line and never ends; write the pattern so that it cannot match its own text, e.g. `'scripts/ig_[a-z]+\.py'`.
- **Collections:** the `saved_collection_ids` field in the feed API does not show all members. Read membership from `/api/v1/feed/collection/<id>/posts/` (`chrome-snippets.md` snippet 3). **The date a post was saved is not in Instagram's web data** (only the publish date `taken_at`); for the real date you need the account data export (Accounts Center).
- **Bulk list and meta:** `/api/v1/feed/saved/posts/` with pagination (~20 posts per page, ~1 s apart) returns caption, account, date (`taken_at`), type and carousel/photo image URLs for all saved posts in one scan. Result to the clipboard → `$W/saved-feed.json` → `ig_import_feed.py` downloads the media (the URLs are signed and expire; take a fresh dump right before downloading). In the dump, `media_type` is 1 photo, 2 video, 8 carousel.
- **Adding new posts:** `ig_state.py add-list --append-new --limit N` adds only codes that are not in state, continues numbering from the current highest order and never changes an existing order. Plain `add-list` (no flag) **rewrites** the order to match the list: do not run it with a partial list.
- **yt-dlp on carousels:** some carousels (with video slides) fail in yt-dlp with "No video formats found"; get them through `ig_import_feed.py`. Frames/OCR still work on carousels with video.
- **Verification script:** the spreadsheet's `No` column is written as text (`clean()` turns everything into str); match the types when comparing with state.

## Limits
- Automating an Instagram account carries risk: do not shorten the delays, keep batches small, stop if the account shows a warning.
- OCR is weak on stylised fonts and busy backgrounds; the confidence score alone is not reliable (a half-read line can still score high).
- Whisper makes mistakes on short/noisy audio; speech detection depends on the `audio_min_mean_volume_db` threshold.
- Media, frames and the working folder are personal data; they never go to a public address and are never committed.
