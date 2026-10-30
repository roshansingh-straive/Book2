# Shelf Check

Upload a bookshelf photo, identify readable titles and compare them with a selected
shelf catalogue. The interface separates **title identity**, **estimated photo
location** and **shelf assignment**. Demo catalogues and stock records are simulated;
no action writes to a real inventory system.

## Run on Windows

Use Python 3.13 and Node.js 22.12 or newer. From the repository folder:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm --prefix app ci
.\run_demo.ps1
```

Open **http://127.0.0.1:8000**. The launcher builds the frontend and starts FastAPI.
Stop with Ctrl+C; run the launcher again to restart. If port 8000 is occupied:

```powershell
$env:PORT = "8001"
.\run_demo.ps1
```

The direct API startup command (after building with `npm --prefix app run build`):

```powershell
.\.venv\Scripts\python.exe -m uvicorn server.main:app --host 127.0.0.1 --port 8000
```

## Run on macOS / Linux

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
npm --prefix app ci
./run_demo.sh
```

Use `PORT=8001 ./run_demo.sh` for another local port. The app binds to loopback by
default. This is a local demo, not a multi-user production deployment.

## Present the demo

1. Select **Explore a sample** to open saved benchmark readings without signing in
   or making an inference request.
2. For a live scan, sign in with your Straive account, upload a JPG, PNG or WebP
   under 20 MB / 40 megapixels, and select the matching reference shelf. The form
   shows a thumbnail to make that selection clear.
3. Select **Analyze photo** on the analysis page. Opening the page or refreshing it
   never automatically starts a paid scan. A large photo can require many requests;
   progress and cancellation remain available.
4. Inspect titles and their separate catalogue/location labels. Outlines are off
   initially; single-pass boxes are labelled estimates, and historical two-pass boxes require
   agreement before being shown. A readable title with an uncertain box remains listed and can match the catalogue.
5. If most identified titles belong to another demo shelf, review the shelf
   suggestion. Changing the comparison shelf reuses the saved readings, retains the
   original image and makes **no model calls**.
6. Review checks as needed. Acknowledging one records it only in this browser
   session. It does not increase coverage or update inventory.

| Photo in `app/public/photos` | Matching demo shelf |
| --- | --- |
| `a.jpg` | A1 · Art Theory & Philosophy |
| `b.jpg` | A2 · Classical Art & Renaissance |
| `c.png` | F2 · Manga & Pop Culture |
| `d.jpg` | M1 · Wellness & Modern Thought |
| `e.jpg` | F1 · General Fiction & Classics |
| `f.jpg` | F3 · Fiction & Bestsellers |

In particular, `e_transposed.jpg` is a rotated/normalized copy of **e.jpg** and
belongs with **F1**, not M1. Other shelf photos can be read, but these six fixed demo
catalogues may not describe their expected contents. Exact within-shelf slots are
not defined; the app does not claim to validate them.

## Straive sign-in

The existing company integration is preserved:

- Browser session: `https://llmfoundry.straivedemo.com/token`, with credentials included.
- Login: the same host's `/login?next=<encoded return URL>`.
- Inference: `https://llmfoundry.straivedemo.com/gemini/v1beta/models/gemini-3.1-pro-preview:streamGenerateContent?alt=sse`.
- Authorization: `Bearer <session token>:llmproxy-playground`.

Authentication and inference use the same Straive demo host. The token stays
in transient browser memory and is sent in the Authorization header to the local
loopback backend, which uses HTTPS for the gateway. No personal provider API key
is required. Model names are hidden in the product interface.

The user reports successful inference on the office laptop. Development regression
checks mock authentication and model responses; they do not establish live office
network access. Use the company-approved network/proxy/certificate configuration.
The app keeps TLS verification enabled. Authentication, permissions, rate limits,
network failure, timeout and incomplete model replies are surfaced explicitly.

An optional one-request diagnostic is available. It reads a token through a hidden
terminal prompt and does not save it:

```powershell
.\.venv\Scripts\python.exe qa\probe_foundry_vision.py --hi
.\.venv\Scripts\python.exe qa\probe_foundry_vision.py
```

The first command sends text only. The second sends the included public shelf crop.
Run these only when a real gateway request is intended. Reports are gitignored.

## Model comparison results

The Model Comparison page reads `app/public/data/model_comparison_results.json`
when present, so saved results can be deployed with the application without running
inference on page load. To refresh it, run the opt-in comparison script with the
desired images and models; it writes the static file after the run completes:

```powershell
.\.venv\Scripts\python.exe qa\compare_models.py --run --all-images --models gemini gpt pro
```

This makes live, potentially billable requests. Commit the generated JSON file and
deploy the updated app to publish those results. The archived per-run reports remain
under the gitignored `qa/model_comparison_results` folder.

## Validation behavior

- Native-resolution, overlapping 1,400-pixel crops with 20% overlap. Each section
  is read once, with no rotated reread. For the 24 MP reference photo this means
  20 base requests instead of 40. Output-limited sections may still need bounded
  smaller crops; actual progress includes those requests. No catalogue or prior
  candidate titles are supplied to recognition calls.
- New single-pass results say **Catalogue matched**, **Single reading** and
  **Not independently verified**. Catalogue coverage counts eligible name matches;
  it is not OCR accuracy, independent confirmation or physical stock verification.
  Historical two-pass results retain their agreement/provisional distinctions.
  Available single-reading location estimates can be shown as optional dashed
  outlines; unknown locations remain unoutlined.
- New requests use the documented `box_2d: [ymin, xmin, ymax, xmax]` integer
  format normalized to 0–1000, with an explicit `coordinate_system` tag. All four
  coordinates are converted together. Legacy fractional boxes remain supported;
  unlabelled pixels, percentages or mixed units are never guessed. Readable titles
  survive with unavailable locations, without extra requests just to repair boxes.
  See [Gemini image understanding](https://ai.google.dev/gemini-api/docs/image-understanding#object-detection).
- Uncertain/inferred text, a single clear reading, incompatible authors, ambiguous
  catalogue identities and different volume numbers remain conservative review
  cases. A single-pass match is provisional and cannot trigger a stock correction.
- Author affixes and generic labels such as “the autobiography” are removed from
  title identity while original transcriptions remain available. Uniquely resolved,
  supported aliases share their evidence instead of creating duplicate book cards.
  Coauthor names and explicit parenthetical transliterations are accepted without
  inventing authors. Distinct volume markers and ambiguous identities remain separate.
- Author-only text, unknown-title placeholders and uncertain fragments are excluded
  from the book-candidate count and retained in a separate expandable text section.
  Location-only uncertainty is summarized once; each title retains its location
  badge. Provisional title checks and unlisted-book checks remain actionable.
- Catalogue matching is one-to-one. An identified/provisional catalogue title is
  not simultaneously listed as missing merely because its box is uncertain.
- Stable per-bay inventory IDs preserve repeated titles across shelves. Identical
  valid allocations prefer the selected shelf rather than inventing a relocation.
- Shelf title coverage measures independently identified local titles divided by
  expected catalogue titles. It is not an accuracy score or physical copy count.
- Titles absent from recognition have **presence unconfirmed**. An unread title
  does not establish a stockout. A title absent from the demo catalogue is labelled
  **Not in demo catalogue**, rather than incorrectly read.

Completed uploads are saved atomically per image and comparison shelf. Refresh
restores the image and result without another model call; a failed rescan retains
the previous completed result. Older saved results with reading evidence are
recompared under the current rules on load, without paid inference. When its
original completed audit is present and matches the uploaded image hash, the app
reparses those raw replies so title variants can be checked again. Without an audit,
saved evidence is used conservatively; legacy boxes remain unconfirmed. Original
audits are never modified. Company tokens,
uploads and run audits are gitignored.

JPEGs with Apple multi-picture (MPF/MPO) metadata are supported by decoding the
primary image frame and applying EXIF orientation, consistent with browser display.

## Reproducible demo data

All inputs needed to regenerate the shipped demo are included:

```sh
.venv/bin/python pipeline/build_store.py
.venv/bin/python pipeline/run_replay_scans.py
```

`pipeline/demo_books.json` is the frozen catalogue seed from the reference benchmark.
`pipeline/benchmark_sources.json` stores selected saved predictions and their source
paths. Recognition has no access to these seeds or planted exceptions. The original
benchmark checkout is optional and is not needed to start the app or regenerate
these assets.

The report's historical model scores do not measure this app's live company model,
crop harness or uploaded-image accuracy. No improved recognition accuracy is claimed
without evaluating fresh outputs. Tile settings are engineering choices, not proven
optima. Saved sample replies have no annotated title locations, measured runtime,
measured cost or calibrated confidence; those fields are explicitly unavailable.

Reference: [Bookshelf Benchmark](https://atharva-729.github.io/bookshelf-benchmark/).

## Verification

```sh
.venv/bin/python -m pytest -q
npm --prefix app run build
node --experimental-strip-types --test qa/test_scan_stream.mjs qa/test_foundry_auth.mjs
```

On Windows use `.\.venv\Scripts\python.exe` instead of `.venv/bin/python`.
Optional scorer tests skip when the reference checkout is absent.

With Playwright and Chrome installed, start the app, set `SHELF_CHECK_URL` to its
local address, and run:

```sh
node qa/check_accuracy_ui.cjs
node qa/check_upload_ui.cjs
node qa/check_validation_ui.cjs
```

`PLAYWRIGHT_MODULE` and `CHROME_PATH` can point to an existing installation. On Windows
`PYTHON` can override the venv executable used by the validation browser check.
These checks block paid inference. They cover all six samples, real local uploads,
explicit scan initiation, saved-result refresh, failure/cancellation, title versus
location separation, real shelf recomparison, and desktop/tablet/mobile layouts.


## Recheck a saved run without inference

Refreshing an older completed upload upgrades its deterministic validation to
comparison version 5 automatically. Restart the server after updating the source.
Do not click **Start fresh scan** unless another paid model run is intended.

For an exported analysis plus audit (including two JSON objects pasted into one file):

```sh
.venv/bin/python qa/reprocess_saved_run.py saved-run.txt --output corrected-analysis.json
# Or separate input files:
.venv/bin/python qa/reprocess_saved_run.py analysis.json --audit audit.json --output corrected-analysis.json
```

Inputs are preserved. This utility does not access the company gateway or change
inventory. The recorded public-image regression and its measured postprocessing
changes are documented in [qa/LIVE_RUN_REVIEW.md](qa/LIVE_RUN_REVIEW.md). The new
box-output contract still requires a fresh office-network scan to assess live
localization quality; offline validation cannot establish that improvement.


## Compare the saved first pass without rotation or rereading

```sh
.venv/bin/python qa/reprocess_saved_run.py saved-run.txt --first-pass-only --output first-pass-analysis.json
```

This selects only the original audit's `read` replies, not its `verify` replies.
It makes zero new inference requests and does not modify the original analysis.
The exported result is labelled `offline_reprocess`; combined runtime/token usage
are cleared because they do not measure the selected subset.

For the supplied public F1 run, the first pass resolves 91 local catalogue
identities versus 98 from both passes when provisional matches are included.
The 81 independently corroborated two-pass matches use a stricter standard and
must not be compared directly with the 91 single-reading matches. Independent
verification is explicitly zero in the single-pass result. See
[qa/SINGLE_PASS_REVIEW.md](qa/SINGLE_PASS_REVIEW.md).
# Book2
