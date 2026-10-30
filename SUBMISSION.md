# Shelf Check — submission handoff

## What changed

Correctly read titles keep their catalogue identity when model boxes are uncertain.
The app displays title identity, estimated location and shelf assignment separately.
Unconfirmed boxes are not drawn, and a located-title disagreement does not also
create a false missing alert. Uncertain text and distinct volumes still require
conservative review.

The selected-shelf mismatch from the reported screenshot is addressed with a
reference-photo preview, an evidence-based shelf suggestion and deterministic
recomparison of completed readings. Changing M1 to F1 preserves the uploaded photo
and makes no new inference requests. Existing saved readings are migrated without
rerunning the model when their evidence is available.

The demo catalogue uses stable per-bay IDs, preserving Atomic Habits and other
repeated titles. Sample responses have reproducible included inputs, no invented
boxes or cost/latency/confidence. Original Apple MPF/MPO JPEGs are accepted by
processing their primary frame. The UI hides model names, avoids red error styling
for uncertain locations and keeps review actions separate from real inventory.

## Verification on 27 October 2026

- Production frontend build passed.
- Python suite: 128 passed in development, including 2 optional external-benchmark checks. Those 2 skip when the reference checkout is absent.
- JavaScript authentication and stream suite: 10 passed.
- Browser sample checks passed: all six shelves, zoom, information modal, review,
  reset, simulated completion/failure/cancellation and stale-result protection.
- Browser upload checks passed: actual local uploads, validation, drag/drop,
  preserved bytes, explicit scan start, reload, history and retained results.
- Screenshot regression passed through actual local upload, storage and comparison
  APIs: exact title kept, unreliable box hidden, wrong-shelf suggestion corrected,
  no duplicate missing alert and no inference on correction or refresh.
- Desktop, tablet and mobile layouts checked for horizontal overflow and visually
  inspected. Browser tests block paid inference.

The user reports the prior company model integration works on the office laptop.
This development run used mocked model responses and made no company inference
requests. Real recognition accuracy and the office SSO session have not been
remeasured by these changes. Model boxes remain estimates, and no exact book-slot
planogram or real ERP system is connected.

## Demonstration

1. Follow the Windows setup in README.md and run `run_demo.ps1`.
2. Open http://127.0.0.1:8000 and sign in with the company account.
3. For the photo from the reported screenshot (`e.jpg` / `e_transposed.jpg`), choose
   **F1 · General Fiction & Classics**, rather than M1.
4. Upload, then click **Analyze photo** once. Inspect the titles and separate
   location badges. An uncertain box does not make a correctly identified title
   wrong.
5. To change the comparison shelf after scanning, use the shelf selector or the
   suggested-shelf button. This reuses the saved readings without another model
   call. Reloading also restores completed results.

For a presentation without network access, use **Explore a sample**. These are
explicitly labelled saved benchmark readings, not a new live scan.

Screenshots named `validation_*` illustrate deterministic regression inputs, not
claims about fresh live model output. See README.md for commands and limitations.


## Follow-up from the real saved run

Comparison version 4 additionally consolidates supported title variants, accepts
coauthor/explicit transliteration aliases, quarantines author-only/uncertain text and weak duplicate aliases,
and summarizes uncertain locations instead of generating a task for every box.
The same recorded replies now produce 81 independently corroborated local catalogue
matches rather than 75. These are postprocessing results, not newly measured model
accuracy. See qa/LIVE_RUN_REVIEW.md for the complete before/after and limitations.
Restart and refresh the existing uploaded analysis to recheck its saved replies
without another paid model call.


## Single-pass default requested after the live-run review

New live scans read each section once. Rotated verification is disabled by default;
a 20-section photograph therefore has 20 base requests, with extra subcrops only
if a reply exceeds the output limit or contains no usable title evidence.
The UI distinguishes catalogue matching from independent verification. Existing
completed runs keep their original method; a fresh scan is needed to run the new
single-pass pipeline. Historical first-pass replies can also be selected offline,
without inference, using qa/reprocess_saved_run.py --first-pass-only.
