"""Conservative title matching and review tasks. No access to benchmark labels.

Title normalization and variant scoring follow the benchmark's evaluate.py,
with additional safeguards for series numbers, short titles and ambiguity.
"""
import re
from difflib import SequenceMatcher

THRESHOLD = 0.85


from server.text import normalize, title_key, clean_title, author_aliases, authors_compatible


def volume_markers(title):
    romans = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8, "ix": 9, "x": 10}
    return [romans.get(value, value) for value in re.findall(r"\b(?:vol|volume|part|book|episode)\s+([ivx]+|\d+)\b", normalize(title))]


def title_score(a, b):
    left, right = title_key(a), title_key(b)
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    # Distinct volumes, sequels or editions cannot be rescued by fuzzy matching.
    if re.findall(r"\d+", left) != re.findall(r"\d+", right) or volume_markers(left) != volume_markers(right):
        return 0.0
    # A main/series label alone does not establish the subtitled volume. The
    # benchmark explicitly calls out "Diary of a Wimpy Kid" as too vague.
    if ((":" in b and left == title_key(b.split(":", 1)[0]))
            or (":" in a and right == title_key(a.split(":", 1)[0]))):
        return 0.0
    if min(len(left), len(right)) < 8:
        return 0.0
    def variants(title):
        result = {title_key(title)}
        main = re.split(r"[:(/]", title)[0]
        if len(title_key(main).split()) >= 3:
            result.add(title_key(main))
        return result
    score = 0.0
    for p in variants(a):
        for g in variants(b):
            score = max(score, SequenceMatcher(None, p, g).ratio(),
                        SequenceMatcher(None, " ".join(sorted(p.split())), " ".join(sorted(g.split()))).ratio())
            short, long = sorted((p.split(), g.split()), key=len)
            if len(short) >= 3 and short in (long[:len(short)], long[-len(short):]):
                score = max(score, 0.90)
    # A partial two-word franchise label is not a full title.
    short, long = sorted((left.split(), right.split()), key=len)
    if len(short) <= 2 and len(long) > len(short) and short == long[:len(short)]:
        return 0.0
    return score


def evidence_title_score(book, item):
    score = title_score(book["title"], item["title"])
    left, right = title_key(book["title"]), title_key(item["title"])
    if not left or not right or re.findall(r"\d+", left) != re.findall(r"\d+", right) or volume_markers(left) != volume_markers(right):
        return score
    if not book.get("author") or not authors_compatible(book["author"], item.get("author")):
        return score
    # A complete, distinctive subtitle can identify a volume even when its
    # series label was not read. A series heading alone still never qualifies.
    if ":" in item["title"]:
        subtitle = title_key(item["title"].split(":", 1)[1])
        if left == subtitle and len(left.split()) >= 2 and len(left) >= 12:
            score = max(score, .96)
    # A fully read long catalogue title plus an additional subtitle is a safe
    # candidate when author and all numbers agree. Short series labels are not.
    if ":" in book["title"] and right == title_key(book["title"].split(":", 1)[0]):
        significant = [w for w in right.split() if w not in {"the", "a", "an", "of", "and", "for", "in", "to"}]
        if len(significant) >= 4 and len(right) >= 20:
            score = max(score, .96)
    return score


def catalogue_choice(book, catalogue, bay_id, index=None):
    exact = (index or {}).get(title_key(book["title"]), [])
    eligible = [(1.0, item) for item in exact] if exact else sorted(((evidence_title_score(book, item), item) for item in catalogue), key=lambda pair: pair[0], reverse=True)
    eligible = [(score, item) for score, item in eligible if score >= THRESHOLD]
    if not eligible:
        return None, 0, "catalogue_unlisted"
    compatible = [(score, item) for score, item in eligible if authors_compatible(book.get("author"), item.get("author"))]
    if not compatible:
        return None, 0, "author_conflict"
    best, target = compatible[0]
    close = [(score, item) for score, item in compatible if best - score < .04]
    if len(close) > 1:
        identities = {(title_key(item["title"]), normalize(item.get("author"))) for _, item in close}
        local = [item for _, item in close if item["assigned_bay_id"] == bay_id]
        if best == 1 and len(identities) == 1 and len(local) == 1:
            target = local[0]
        else:
            return None, best, "catalogue_ambiguous"
    return target, best, None


def prepare_candidates(observations, catalogue, bay_id, choose):
    """Consolidate supported aliases; quarantine fragments without erasing them."""
    from server.recognition import merge_readings
    known_titles = {title_key(item["title"]) for item in catalogue}
    known_authors = {alias for item in catalogue for alias in author_aliases(item.get("author"))}
    candidates, unresolved, groups = [], [], {}
    for original in observations:
        book = {**original, "title": clean_title(original["title"], original.get("author"))}
        book["title_variants"] = list(dict.fromkeys([*original.get("title_variants", []), original["title"]]))
        key = title_key(book["title"])
        placeholder = key not in known_titles and key in {"unknown", "unknown title", "unreadable", "unreadable title", "untitled", "illegible", "title unknown"}
        author_only = key not in known_titles and (normalize(book["title"]) in known_authors or key == title_key(book.get("author")))
        if placeholder or author_only or book.get("title_status") == "uncertain" or (len(key) <= 2 and key not in known_titles):
            unresolved.append({**book, "exclusion_reason": "placeholder" if placeholder else "author_only" if author_only else "uncertain_text"})
            continue
        target, score, reason = choose(book)
        # Group raw-evidence candidates only when their catalogue identity is
        # uniquely resolved. Never merge distinct volumes or ambiguous authors.
        if target and book.get("evidence") and score >= .90:
            groups.setdefault(target["sku"], []).append(book)
        else:
            candidates.append(book)
    for entries in groups.values():
        if len(entries) == 1:
            candidates.append(entries[0])
            continue
        representative = max(entries, key=lambda book: (book.get("title_status") == "agreed", len(title_key(book["title"]))))
        evidence = []
        variants = []
        for book in entries:
            variants.extend(book["title_variants"])
            for entry in book["evidence"]:
                evidence.append({**entry, "title": representative["title"], "author": representative.get("author"),
                                 "source_title": book["title"]})
        consolidated = merge_readings(evidence, single_pass=representative.get("reading_mode") == "single_pass")[0]
        consolidated["title_variants"] = list(dict.fromkeys(variants))
        consolidated["merged_variant_count"] = len(entries)
        candidates.append(consolidated)
    candidates.sort(key=lambda book: (choose(book)[0] is None, book.get("title_status") not in {"agreed", None}))
    return candidates, unresolved


REVIEW_MESSAGES = {
    "title_uncertain": "The visible title text is incomplete or uncertain.",
    "single_read": "This title was readable in one pass; an independent reading did not confirm it.",
    "position_unconfirmed": "The estimated box was not confirmed across both readings.",
    "overlapping_boxes": "Estimated boxes overlap other titles. Confirm the location in the photo.",
    "author_conflict": "The title matches, but the read author conflicts with the catalogue.",
    "catalogue_ambiguous": "More than one catalogue identity fits this reading.",
    "duplicate_identity": "Another reading already represents this catalogue title. Review copies or title variants.",
    "catalogue_unlisted": "This title is not listed in the demo catalogue; this does not mean it was read incorrectly.",
    "legacy_review": "This saved reading needs a fresh verification before it can be confirmed.",
}


def compare_books(store, bay, observations, *, reading_mode="verified"):
    """Identify books separately from box quality and shelf assignment.

    A clear text match can reserve its catalogue identity while its estimated
    position needs review. Such a title is not also reported missing. Uncertain
    or inferred text never becomes a confirmed identity or inventory correction.
    """
    if reading_mode not in {"verified", "single_pass"}:
        raise ValueError("Unsupported reading mode")
    review_messages = {**REVIEW_MESSAGES}
    if reading_mode == "single_pass":
        review_messages["position_unconfirmed"] = "No usable location estimate was available from this reading."
    catalogue = list(store["catalogue"].values())
    raw_candidates = len(observations)
    recognition_readings = observations
    index, cache = {}, {}
    for item in catalogue:
        index.setdefault(title_key(item["title"]), []).append(item)
    def choose(book):
        key = (book["title"], book.get("author"))
        if key not in cache:
            cache[key] = catalogue_choice(book, catalogue, bay["id"], index)
        return cache[key]
    observations, unresolved = prepare_candidates(observations, catalogue, bay["id"], choose)
    assigned = [p for p in catalogue if p["assigned_bay_id"] == bay["id"]]
    bays = {b["id"]: b for b in store["bays"]}
    candidates, reasons = [], {}
    for i, book in enumerate(observations):
        why = list(book.get("review_reasons", []))
        reasons[i] = why
        if book.get("title_status") == "uncertain":
            why.append("title_uncertain")
            continue
        if book.get("verification_status") == "needs_review" and not book.get("title_status"):
            why.append("legacy_review")
            continue
        target, best, reason = choose(book)
        if reason:
            why.append(reason)
            continue
        candidates.append((best, i, target))

    matched, used_skus, owners, possible_duplicates = {}, set(), {}, {}
    # Strong independently agreed text gets first choice over a single-pass
    # variant; otherwise source order must not decide the identified title.
    for score, i, target in sorted(candidates, key=lambda x: (observations[x[1]].get("title_status") == "single_read", -x[0], x[1])):
        if target["sku"] in used_skus:
            owner = owners[target["sku"]]
            if observations[owner].get("title_status") == "agreed" and observations[owner].get("evidence") and observations[i].get("evidence"):
                # A weaker alias of an already independently identified book is
                # inspectable text, not an additional unique book or a new vote.
                possible_duplicates[i] = (owner, target)
            else:
                reasons[i].append("duplicate_identity")
            continue
        matched[i] = target
        owners[target["sku"]] = i
        used_skus.add(target["sku"])

    for i, (owner, target) in possible_duplicates.items():
        observations[owner] = {**observations[owner], "unconfirmed_variants": list(dict.fromkeys([*observations[owner].get("unconfirmed_variants", []), observations[i]["title"]]))}
    items, tasks, misplaced = [], [], []
    for i, book in enumerate(observations):
        if i in possible_duplicates:
            _, related = possible_duplicates[i]
            unresolved.append({**book, "exclusion_reason": "possible_duplicate", "related_title": related["title"]})
            continue
        target = matched.get(i)
        why = list(dict.fromkeys(reasons[i]))
        if reading_mode == "single_pass":
            why = [reason for reason in why if reason != "single_read"]
        identity_uncertain = any(reason in why for reason in ("title_uncertain", "single_read", "author_conflict", "catalogue_ambiguous", "duplicate_identity", "legacy_review"))
        status = "needs_review" if identity_uncertain else "unexpected" if not target else "matched" if target["assigned_bay_id"] == bay["id"] else "misplaced"
        destination = bays.get(target["assigned_bay_id"], {}).get("name") if target else None
        item = {
            **book, "id": f"{bay['id']}-item-{i+1}", "confidence": None,
            "review_reasons": why,
            "catalogue_status": "matched" if target else "unlisted" if status == "unexpected" else "needs_review",
            "status": status,
            "status_label": {"matched": "Catalogue matched" if reading_mode == "single_pass" else "Title matched", "misplaced": "Assigned to another shelf", "unexpected": "Not in demo catalogue", "needs_review": "Title needs confirmation"}[status],
            "catalogue_title": target["title"] if target else None,
            "sku": target["sku"] if target else None,
            "price": target["price"] if target else None,
            "misplaced_reason": f"Selected shelf: {bay['name']}. Catalogue assignment: {destination}." if status == "misplaced" else None,
            "target_bay_name": destination if status == "misplaced" else None,
        }
        items.append(item)
        if status == "misplaced":
            misplaced.append(item)
            tasks.append({"id": f"{bay['id']}-move-{target['sku']}", "type": "misplaced_item", "severity": "warning", "badge": "Check shelf assignment", "title": book["title"], "author": book.get("author"), "sku": target["sku"], "headline": f"Title identified here; the demo catalogue assigns it to {destination}. Confirm the selected comparison shelf first.", "suggested_action": "Review shelf assignment", "shelf_item_id": item["id"], "requires_review": True})
        if why:
            location_only = target and not identity_uncertain and all(reason in {"position_unconfirmed", "overlapping_boxes"} for reason in why)
            if not location_only:
                tasks.append({"id": f"{bay['id']}-review-{i+1}", "type": "recognition_review", "severity": "medium", "badge": "Title matched · Location unconfirmed" if location_only else "Catalogue check" if status == "unexpected" else "Title confirmation", "title": book["title"], "author": book.get("author"), "headline": " ".join(review_messages.get(reason, "Inspect the original photo.") for reason in why), "suggested_action": "Review photo location" if location_only else "Inspect photo and confirm title", "shelf_item_id": item["id"], "requires_review": True})
        if target and not identity_uncertain and book.get("title_status") != "single_read" and target["simulated_on_hand"] == 0:
            tasks.append({"id": f"{bay['id']}-record-{target['sku']}", "type": "record_error", "severity": "high", "badge": "Check inventory record", "title": book["title"], "author": book.get("author"), "sku": target["sku"], "headline": "Title identified in the photo; the simulated record shows 0. Verify the physical count before changing records.", "suggested_action": "Confirm physical count and record check", "system_on_hand": 0, "shelf_item_id": item["id"], "requires_review": True})

    missing = []
    for p in assigned:
        if p["sku"] in used_skus:
            continue
        missing.append({"sku": p["sku"], "title": p["title"], "author": p.get("author"), "planogram_bay_id": bay["id"], "simulated_on_hand": p["simulated_on_hand"], "price": p["price"], "sales_velocity": p["sales_velocity_units_per_day"], "is_phantom_inventory": False, "reason": "Title not identified in this photo; it may be unreadable or occluded.", "action": "Check shelf before changing inventory", "requires_review": True})
        tasks.append({"id": f"{bay['id']}-unseen-{p['sku']}", "type": "missing_item", "severity": "medium", "badge": "Presence unconfirmed", "title": p["title"], "author": p.get("author"), "sku": p["sku"], "headline": f"Title not identified in the photo. Simulated on-hand: {p['simulated_on_hand']}. This does not establish a stockout.", "suggested_action": "Confirm shelf and backroom check", "system_on_hand": p["simulated_on_hand"], "requires_review": True})
    correct = sum(item["status"] == "matched" for item in items)
    counts = {}
    for i, target in matched.items():
        if observations[i].get("title_status") != "single_read":
            counts[target["assigned_bay_id"]] = counts.get(target["assigned_bay_id"], 0) + 1
    strongest = max(counts, key=counts.get) if counts else None
    suggestion = None
    if strongest and strongest != bay["id"] and counts[strongest] >= 3 and counts[strongest] > 2 * counts.get(bay["id"], 0) and counts[strongest] / sum(counts.values()) >= .6 and bays.get(strongest, {}).get("scannable"):
        suggestion = {"bay_id": strongest, "bay_name": bays[strongest]["name"], "matching_titles": counts[strongest], "message": "Most identified catalogue titles belong to another demo shelf. Check the comparison shelf before reviewing individual placement alerts."}
    return {
        "comparison_version": 5,
        "reading_mode": reading_mode,
        "recognition_readings": recognition_readings,
        "unresolved_readings": unresolved,
        "candidate_cleanup": {"input_groups": raw_candidates, "displayed_titles": len(items), "unresolved_groups": len(unresolved), "merged_alias_groups": raw_candidates - len(unresolved) - len(items)},
        "comparison_suggestion": suggestion,
        "planogram_items": assigned, "shelf_items": items, "misplaced_items": misplaced,
        "missing_items": missing, "action_tasks": tasks,
        "metrics": {"planogram_expected_items": len(assigned), "shelf_items_detected": len(items), "matched_count": correct, "independent_verified_count": sum(item["status"] == "matched" and item.get("title_status") == "agreed" for item in items), "catalogue_matched_count": len(matched), "missing_count": len(missing), "misplaced_count": len(misplaced), "review_count": sum(task["type"] == "recognition_review" for task in tasks), "location_review_count": sum(item.get("position_status") == "needs_review" for item in items), "provisional_count": sum(item["catalogue_status"] == "matched" and item["status"] == "needs_review" for item in items), "planogram_compliance_pct": round(100 * correct / len(assigned), 1) if assigned else 100.0},
    }
