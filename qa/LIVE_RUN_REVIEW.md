# Review of the supplied live run

The user supplied both the completed F1 analysis and its complete 40-request audit
for the public benchmark photograph e.jpg. This review reprocesses the same stored
model replies; it makes no new inference requests and does not alter the original
audit. A reduced fixture in fixtures/live_e_replies.json contains only public-image
transcriptions, crop dimensions and completion flags. Personal/run identifiers,
image hashes, credentials, usage records and image bytes are omitted.

## Verified causes

- 392 raw reading observations became 190 exact-normalized title groups. They were
  presented as “unique titles,” including author-only text and uncertain fragments.
- 137 of those observations had invalid fractional boxes: 123 in the read pass and
  14 in the verification pass. Raw replies used pixel-like or mixed-unit values.
  Their units cannot safely be recovered by guessing. Location agreement remained
  separate from title agreement, but location-only tasks overwhelmed the feed.
- “Speaking for Myself: the autobiography” and “Speaking for Myself” were read in
  different passes and kept as separate single-pass candidates.
- “Leading” was read clearly in both passes but rejected because “Alex Ferguson”
  did not satisfy the old check against “Alex Ferguson with Michael Moritz.”
- Author prefixes, partial series labels and title variants created additional
  duplicate or unlisted candidates. Explicit Hindi/Latin author aliases also
  caused an avoidable mismatch.

## Same-reply postprocessing results

| Measure | Supplied analysis | Updated validation |
| --- | ---: | ---: |
| Displayed title groups / candidates | 190 | 132 |
| Independently corroborated local catalogue matches | 75 | 81 |
| Provisional local catalogue matches | 20 | 17 |
| Expected titles still unconfirmed | 15 | 12 |
| Shelf assignment checks | 1 | 1 |
| Individual title/catalogue review checks | 170 | 50 |
| Shelf title coverage | 68.2% | 73.6% |

The old provisional count is derived from 96 catalogue allocations minus 75 local
confirmed titles and 1 other-shelf title. The new 81 confirmed + 17 provisional +
12 unconfirmed reconcile to the 110 expected catalogue titles. Another title is
assigned to a different shelf.

The new title count is explicitly **candidates**, not a claim that all 132 are
correct distinct books. 42 unresolved groups remain inspectable but are excluded
from that count. 105 uncertain location estimates remain disclosed in one summary
and per-title detail badges, rather than being hidden or treated as wrong names.

The six newly corroborated catalogue identities are:

- Tom Gates: Everything's Amazing (Sort Of)
- The Wimpy Kid Do-It-Yourself Book
- Stranger Things: Suspicious Minds
- Horrible Science: Disgusting Digestion
- Leading
- Speaking for Myself

These identifications rely on existing clear visible-text evidence and independently
recorded passes. Catalogue information is still never supplied to model calls.
Uncertain text is not promoted merely because a catalogue entry is available.
The Winner Stands Alone and Hunted remain unconfirmed; no reading was manufactured
to fill the catalogue. Three extra titles are intentionally absent demo stock.

## Boundaries

No new model accuracy, precision or recall is established by this review. “Shelf
coverage” measures validation against the simulated catalogue, including its
limitations. Ambiguous or absent box coordinates are not repaired retroactively.

Future requests now use the explicit integer corner-box format documented by
[Gemini](https://ai.google.dev/gemini-api/docs/image-understanding#object-detection),
with local validation and safe fallback to an unknown location. That contract has
mocked/unit coverage and still needs a fresh office-network scan to measure live
localization quality.
