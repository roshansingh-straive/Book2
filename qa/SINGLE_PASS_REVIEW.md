# First-pass-only comparison

The user requested analysis without rotation or rereading. The default live
pipeline now runs only its `read` phase. It retains native-resolution tiling,
EXIF display-orientation correction, schema validation, title cleanup and
catalogue matching. It does not run a rotated verification phase.

The saved public F1 audit was also replayed using only its 20 original `read`
replies. No company model requests were made for this experiment. It is not a
fresh live measurement of the revised prompt or model localization.

| Measure | First pass only | Both saved passes |
| --- | ---: | ---: |
| Recorded requests selected | 20 | 40 |
| Local catalogue identities, including provisional | 91 | 98 |
| Independent corroboration | None | 81 local matches |
| Expected titles unconfirmed | 19 | 12 |

The single-pass pipeline reports `reading_mode=single_pass` and
`rotated_verification=false`. Its title badges explicitly say that matches have
not been independently verified. Catalogue matching is allowed without requiring
an absent second pass. A readable title can therefore match the inventory name,
while stock correction remains unconfirmed and all inventory actions stay manual.

The 91 single-reading matches and 81 independently corroborated two-pass matches
use different evidence standards. Comparing them as if the former were more
accurate would be misleading. The original full runtime and token totals do not
measure the first-pass subset, so the diagnostic export leaves those fields null.

Unit tests assert one request for a one-section image, 20 base requests for the
24 MP grid, original image orientation in the read request, no verify-phase
observations, no falsely agreed titles, correct API persistence/recomparison, and
zero independently verified matches for the recorded single-pass subset.

Validation: production build, 128 Python tests and 10 authentication/stream tests
passed. Chrome checks passed for samples, uploads, and recorded single-pass
results, including explicit estimate labels and no two-reading claims. Company
authentication and inference were mocked or blocked during these checks.
