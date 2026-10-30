"""Accuracy regression cases: geometry, corroboration, matching and API contracts."""
import asyncio
import base64
import io
import json

import httpx
import pytest
from PIL import Image
from pydantic import ValidationError

from server.accuracy import FOUNDRY_GEMINI, select_profile
from server.comparison import compare_books, normalize, title_score
from server.recognition import (
    Box, Readings, RecognitionError, VisionClient, load_image, map_box, map_rotated_subtile_box,
    normalize_recognition_payload, parse_readings, split_rotated_crop,
    merge_readings, provider_schema, run_recognition, tile_image,
)


@pytest.fixture(autouse=True)
def no_real_credentials(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


def image_bytes(size=(100, 50), orientation=None):
    image = Image.new("RGB", size, "white")
    buffer = io.BytesIO()
    if orientation:
        exif = Image.Exif()
        exif[274] = orientation
        image.save(buffer, format="JPEG", exif=exif)
    else:
        image.save(buffer, format="PNG")
    return buffer.getvalue()


def reading(title="Determined", **extra):
    return {"title": title, "author": None, "visible_text": title, "uncertain": False,
            "box": {"top": .2, "left": .1, "width": .3, "height": .4}, **extra}


def response(books, profile=FOUNDRY_GEMINI, complete=True, response_text=None, **overrides):
    candidate = {"content": {"parts": [{"text": response_text if response_text is not None else json.dumps({"books": books})}]},
                 "finishReason": "STOP" if complete else "MAX_TOKENS"}
    payload = {"modelVersion": profile.model_id, "candidates": [candidate],
               "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 20, "thoughtsTokenCount": 7}}
    payload.update(overrides)
    return httpx.Response(200, headers={"content-type": "text/event-stream"},
                          content=f"data: {json.dumps(payload)}\n\n".encode())


@pytest.mark.parametrize("difficulty", ["easy", "medium", "hard"])
def test_foundry_model_is_not_selected_by_unmeasured_benchmark_policy(difficulty):
    assert select_profile() == FOUNDRY_GEMINI


@pytest.mark.parametrize("size", [(100, 90), (1400, 1400), (1401, 1401), (1300, 956), (1080, 1440), (4284, 5712), (5712, 4284)])
def test_tiles_cover_entire_original_without_downscaling(size):
    tiles = tile_image(size)
    assert len({t.bounds for t in tiles}) == len(tiles)
    width, height = size
    # For every horizontal band, the tile intervals must cover the whole width.
    ys = sorted({0, height, *(t.bounds[1] for t in tiles), *(t.bounds[3] for t in tiles)})
    for top, bottom in zip(ys, ys[1:]):
        intervals = sorted((t.bounds[0], t.bounds[2]) for t in tiles if t.bounds[1] <= top and t.bounds[3] >= bottom)
        reached = 0
        for left, right in intervals:
            assert left <= reached
            reached = max(reached, right)
        assert reached == width
    for t in tiles:
        left, top, right, bottom = t.bounds
        assert 0 < right-left <= 1400 and 0 < bottom-top <= 1400
        assert 0 <= left < right <= width and 0 <= top < bottom <= height


def test_oversized_grid_fails_instead_of_skipping_regions():
    with pytest.raises(RecognitionError, match="smaller sections"):
        tile_image((10000, 10000))


@pytest.mark.parametrize("orientation,size", [(1, (100, 50)), (6, (50, 100)), (8, (50, 100))])
def test_exif_orientation_matches_browser_frame(orientation, size):
    assert load_image(image_bytes(orientation=orientation)).size == size


def test_invalid_image_rejected():
    with pytest.raises(RecognitionError, match="decoded"):
        load_image(b"not an image")


def test_rotated_boxes_map_back_to_same_native_location():
    original = {"top": .2, "left": .1, "width": .3, "height": .4}
    rotated = {"top": .1, "left": .4, "width": .4, "height": .3}
    bounds = (1120, 2240, 2520, 3640)
    normal = map_box(original, bounds, (4284, 5712))
    inverse = map_box(rotated, bounds, (4284, 5712), rotated=True)
    assert inverse == pytest.approx(normal)
    assert normal["left"] == pytest.approx(1260/4284)


def test_rotated_subtile_boxes_map_back_to_original_photo_coordinates():
    mapped = map_rotated_subtile_box(
        {"top": 0, "left": 0, "width": 1, "height": 1},
        (0, 0, 55, 27), (100, 50), (100, 200, 150, 300), (300, 500),
    )

    assert mapped == pytest.approx({"top": .49, "left": 1 / 3, "width": .09, "height": .11})


def test_dense_rotated_crop_splits_into_four_overlapping_sections():
    children = split_rotated_crop(Image.new("RGB", (100, 50)))

    assert len(children) == 4
    assert [child_id for child_id, _, _ in children] == ["sub-1", "sub-2", "sub-3", "sub-4"]
    assert all(child.size[0] < 100 and child.size[1] < 50 for _, _, child in children)


@pytest.mark.parametrize("box", [
    {"top": -.1, "left": 0, "width": .1, "height": .1},
    {"top": 0, "left": .9, "width": .2, "height": .1},
    {"top": 0, "left": 0, "width": 0, "height": .1},
    {"top": 0, "left": 0, "width": float("nan"), "height": .1},
    {"top": 0, "left": 0, "width": float("inf"), "height": .1},
])
def test_invalid_geometry_never_becomes_an_outline(box):
    with pytest.raises(ValidationError):
        Box.model_validate(box)


@pytest.mark.parametrize("box", [
    {"top": 956, "left": 0, "width": 255, "height": .093},
    {"top": 218, "left": 0, "width": 140, "height": 781},
    {"top": 8.528, "left": .439, "width": 6.1, "height": 15.8},
    {"top": .2, "left": .1, "width": 101.2, "height": .4},
])
def test_unknown_coordinate_units_retain_text_without_inventing_location(box):
    payload = {"books": [reading(box=box.copy())]}
    parsed, rejected = parse_readings(payload, (1400, 1400))
    assert parsed.books[0].title == "Determined"
    assert parsed.books[0].box is None
    assert not parsed.books[0].uncertain
    assert rejected == 0
    assert payload["books"][0]["box"] == box  # no mutation of raw audit evidence


def test_fractional_coordinates_are_preserved_exactly():
    payload = {"books": [reading()]}
    parsed, _ = parse_readings(payload, (1400, 1400))
    assert parsed.books[0].box.model_dump() == reading()["box"]


def test_unreadable_blank_titles_are_omitted_without_rejecting_other_books():
    payload = {"books": [
        reading("Readable title"),
        reading("", visible_text="Author only"),
        reading("   ", visible_text="Unclear letters"),
    ]}

    parsed = Readings.model_validate(normalize_recognition_payload(payload, (1400, 1400)))

    assert [book.title for book in parsed.books] == ["Readable title"]


def test_invalid_book_box_retains_readable_title_without_a_false_outline():
    payload = {"books": [
        reading("Readable title"),
        reading("Out of bounds", box={"top": .8, "left": .1, "width": .3, "height": .3}),
    ]}

    parsed, rejected = parse_readings(payload, (1400, 1400))

    assert [book.title for book in parsed.books] == ["Readable title", "Out of bounds"]
    assert parsed.books[0].box is not None
    assert parsed.books[1].box is None
    assert rejected == 0


def test_all_invalid_readings_are_not_reported_as_an_empty_valid_section():
    payload = {"books": [reading(123)]}

    with pytest.raises(RecognitionError, match="no valid book readings"):
        parse_readings(payload, (1400, 1400))


def obs(phase="read", title="Determined", **kwargs):
    return {**reading(title), "pass": phase, "tile_id": "tile-1", **kwargs}


def test_overlapping_repeats_do_not_become_extra_titles():
    merged = merge_readings([obs(), obs(tile_id="tile-2"), obs("verify")])
    assert len(merged) == 1
    assert merged[0]["verification_status"] == "verified"
    assert merged[0]["confidence"] is None
    assert len(merged[0]["evidence"]) == 3


def test_same_pass_or_different_location_cannot_corroborate():
    assert merge_readings([obs(), obs(tile_id="tile-2")])[0]["verification_status"] == "needs_review"
    other = obs("verify", box={"top": .8, "left": .8, "width": .1, "height": .1})
    assert merge_readings([obs(), other])[0]["verification_status"] == "needs_review"


def test_conflicting_titles_or_uncertainty_remain_review_items():
    merged = merge_readings([obs(), obs("verify"), obs("verify", title="Behave")])
    assert all(b["verification_status"] == "needs_review" for b in merged)
    assert merge_readings([obs(), obs("verify", uncertain=True)])[0]["verification_status"] == "needs_review"


def test_conflicting_authors_stay_unknown():
    result = merge_readings([obs(author="A"), obs("verify", author="B")])[0]
    assert result["author"] is None


def test_title_normalization_preserves_non_latin_marks_and_numbers():
    assert normalize("Café & Art") == "cafe and art"
    assert normalize("जादू") == "जादू"
    assert normalize("जादू") != normalize("जद")
    assert title_score("The Trial", "Trial") == 1
    assert title_score("Attack on Titan: Volume 1", "Attack on Titan: Volume 2") == 0
    assert title_score("Harry Potter", "Harry Potter and the Goblet of Fire") == 0
    assert title_score("You Can", "You Can Win") == 0
    assert title_score("Diary of a Wimpy Kid", "Diary of a Wimpy Kid: The Long Haul") == 0
    assert title_score("Racine: Modern Judgements", "Modern Judgements: Racine") >= .85


def tiny_store():
    def item(sku, title, bay="bay_a1", on_hand=2):
        return {"sku": sku, "title": title, "author": None, "assigned_bay_id": bay, "price": 10, "simulated_on_hand": on_hand, "sales_velocity_units_per_day": 1}
    bay = {"id": "bay_a1", "name": "Shelf A"}
    store = {"bays": [bay, {"id": "bay_b1", "name": "Shelf B"}], "catalogue": {
        "a": item("a", "Determined"), "b": item("b", "Behave", on_hand=0),
        "c": item("c", "Deep Work", bay="bay_b1"),
    }}
    return store, bay


def test_unrecognized_books_are_not_asserted_stockouts():
    store, bay = tiny_store()
    result = compare_books(store, bay, [])
    assert result["metrics"]["planogram_compliance_pct"] == 0
    assert all(not m["is_phantom_inventory"] for m in result["missing_items"])
    assert all(t["requires_review"] for t in result["action_tasks"])
    assert all("shelf_count" not in t for t in result["action_tasks"])


def test_comparison_uses_inventory_instead_of_planted_answers():
    store, bay = tiny_store()
    result = compare_books(store, bay, [reading("Behave"), reading("Deep Work")])
    assert result["metrics"]["matched_count"] == 1
    assert result["misplaced_items"][0]["target_bay_name"] == "Shelf B"
    assert {t["type"] for t in result["action_tasks"]} == {"record_error", "misplaced_item", "missing_item"}
    assert result["metrics"]["planogram_compliance_pct"] <= 100


def test_uncorroborated_read_cannot_satisfy_planogram_or_trigger_record_correction():
    store, bay = tiny_store()
    result = compare_books(store, bay, [reading("Behave", verification_status="needs_review")])
    assert result["metrics"]["matched_count"] == 0
    assert not any(t["type"] == "record_error" for t in result["action_tasks"])
    assert any(t["type"] == "recognition_review" for t in result["action_tasks"])


def test_catalogue_matching_is_one_to_one_and_does_not_invent_authors():
    store, bay = tiny_store()
    store["catalogue"]["a"]["author"] = "Robert Sapolsky"
    result = compare_books(store, bay, [reading(), reading()])
    assert result["metrics"]["matched_count"] == 1
    assert result["shelf_items"][0]["author"] is None
    assert result["shelf_items"][1]["status"] == "needs_review"


def test_same_book_allocated_to_two_bays_prefers_valid_local_allocation():
    store, bay = tiny_store()
    store["catalogue"]["d"] = {**store["catalogue"]["a"], "sku": "d", "assigned_bay_id": "bay_b1"}
    result = compare_books(store, bay, [reading()])
    assert result["shelf_items"][0]["status"] == "matched"
    assert result["shelf_items"][0]["sku"] == "a"
    assert result["metrics"]["matched_count"] == 1


def test_same_title_by_different_authors_is_ambiguous_without_visible_author():
    store, bay = tiny_store()
    store["catalogue"]["a"]["author"] = "Robert Sapolsky"
    store["catalogue"]["d"] = {**store["catalogue"]["a"], "sku": "d", "author": "Someone Else", "assigned_bay_id": "bay_b1"}
    result = compare_books(store, bay, [reading()])
    assert result["shelf_items"][0]["status"] == "needs_review"


def test_api_schema_compatible_but_local_validation_strict():
    schema = provider_schema()
    encoded = json.dumps(schema)
    for key in ("minimum", "maximum", "minLength", "maxLength", "maxItems", "exclusiveMinimum"):
        assert f'"{key}"' not in encoded
    assert schema["additionalProperties"] is False
    with pytest.raises(ValidationError):
        Readings.model_validate({"books": [reading(visible_text=" ")]})
    with pytest.raises(ValidationError):
        Readings.model_validate({"books": [reading(visible_text="...")]})
    assert Readings.model_validate({"books": [reading(author="???")]}).books[0].author is None
    assert Readings.model_validate({"books": [reading(visible_text="Robert Sapolsky")]}).books[0].uncertain


def test_foundry_payload_uses_gemini_schema_stream_and_ephemeral_token():
    profile = FOUNDRY_GEMINI
    token = "ephemeral-test-token"
    requests = []
    def handler(request):
        body = json.loads(request.content)
        requests.append(request)
        assert str(request.url) == "https://llmfoundry.straivedemo.com/gemini/v1beta/models/gemini-3.1-pro-preview:streamGenerateContent?alt=sse"
        assert request.headers["authorization"] == f"Bearer {token}:llmproxy-playground"
        assert request.headers["content-type"] == "application/json"
        config = body["generationConfig"]
        assert config["temperature"] == 1
        assert config["thinkingConfig"] == {"thinkingLevel": "HIGH"}
        assert config["responseMimeType"] == "application/json"
        assert config["responseJsonSchema"] == provider_schema()
        assert len(body["contents"][0]["parts"]) == 2
        assert "compact JSON on" in body["contents"][0]["parts"][1]["text"]
        return response([reading()], profile)
    client = VisionClient(profile, token, httpx.MockTransport(handler))
    books = asyncio.run(client.read(Image.new("RGB", (10, 10)), "read", "tile-1"))
    assert len(books) == 1 and len(requests) == 1
    assert client.calls[0]["actual_model"] == profile.model_id


@pytest.mark.parametrize("failure", ["truncated", "model_substitution", "invalid_json", "invalid_title"])
def test_incomplete_or_invalid_foundry_responses_are_rejected(failure):
    def handler(request):
        if failure == "truncated":
            return response([reading()], complete=False)
        if failure == "model_substitution":
            return response([reading()], modelVersion="gemini-2.5-pro")
        if failure == "invalid_json":
            return response([], response_text='{"books": [')
        return response([reading(123)])
    client = VisionClient(FOUNDRY_GEMINI, "test-token", httpx.MockTransport(handler))
    with pytest.raises(RecognitionError):
        asyncio.run(client.read(Image.new("RGB", (10, 10)), "read", "tile-1"))


def test_output_limit_is_reported_distinctly_and_logged():
    client = VisionClient(
        FOUNDRY_GEMINI, "test-token",
        httpx.MockTransport(lambda request: response([], complete=False)),
    )

    with pytest.raises(RecognitionError, match="response-size limit") as exc:
        asyncio.run(client.read(Image.new("RGB", (10, 10)), "verify", "tile-19"))

    assert exc.value.code == "output_limit"
    assert client.calls[0]["finish_reason"] == "MAX_TOKENS"
    assert not client.calls[0]["complete"]


def test_authentication_failure_is_not_retried_or_echoed():
    token = "private-test-token"
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(401, text=f"{token} and sensitive response body")
    client = VisionClient(FOUNDRY_GEMINI, token, httpx.MockTransport(handler))
    with pytest.raises(RecognitionError) as exc:
        asyncio.run(client.read(Image.new("RGB", (10, 10)), "read", "tile-1"))
    assert len(requests) == 1
    assert exc.value.code == "authentication"
    assert token not in str(exc.value)


def test_permission_denial_is_distinct_and_provider_errors_do_not_leak():
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(403, text="private upstream detail")
    client = VisionClient(FOUNDRY_GEMINI, "token", httpx.MockTransport(handler))
    with pytest.raises(RecognitionError) as exc:
        asyncio.run(client.read(Image.new("RGB", (10, 10)), "read", "tile-1"))
    assert exc.value.code == "permission"
    assert "private upstream detail" not in str(exc.value)
    assert len(requests) == 1


def test_rate_limit_is_reported_without_retry():
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(429)
    client = VisionClient(FOUNDRY_GEMINI, "token", httpx.MockTransport(handler))
    with pytest.raises(RecognitionError) as exc:
        asyncio.run(client.read(Image.new("RGB", (10, 10)), "read", "tile-1"))
    assert exc.value.code == "rate_limit"
    assert len(requests) == 1


def test_cancellation_closes_the_upstream_stream():
    class WaitingStream(httpx.AsyncByteStream):
        def __init__(self):
            self.started = asyncio.Event()
            self.closed = False

        async def __aiter__(self):
            self.started.set()
            await asyncio.Event().wait()
            yield b""

        async def aclose(self):
            self.closed = True

    stream = WaitingStream()
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=stream)
    client = VisionClient(FOUNDRY_GEMINI, "token", httpx.MockTransport(handler))

    async def run_cancelled_read():
        task = asyncio.create_task(client.read(Image.new("RGB", (10, 10)), "read", "tile-1"))
        await asyncio.wait_for(stream.started.wait(), timeout=1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run_cancelled_read())
    assert stream.closed
    assert len(requests) == 1


def test_total_request_deadline_closes_a_continuously_open_upstream_stream(monkeypatch):
    class SlowStream(httpx.AsyncByteStream):
        def __init__(self):
            self.started = asyncio.Event()
            self.closed = False

        async def __aiter__(self):
            self.started.set()
            await asyncio.Event().wait()
            yield b""

        async def aclose(self):
            self.closed = True

    stream = SlowStream()
    monkeypatch.setattr("server.recognition.INFERENCE_REQUEST_DEADLINE_SECONDS", 0.02)
    client = VisionClient(
        FOUNDRY_GEMINI, "test-token",
        httpx.MockTransport(lambda request: httpx.Response(
            200, headers={"content-type": "text/event-stream"}, stream=stream,
        )),
    )

    async def run_timeout():
        with pytest.raises(RecognitionError) as exc:
            await client.read(Image.new("RGB", (10, 10)), "read", "tile-1")
        assert exc.value.code == "timeout"

    asyncio.run(run_timeout())
    assert stream.closed


def test_sse_fragments_are_joined_and_finish_and_usage_are_required():
    events = [
        {"modelVersion": FOUNDRY_GEMINI.model_id, "candidates": [{"content": {"parts": [{"text": '{"books":'}]}}]},
        {"candidates": [{"content": {"parts": [{"text": f'{json.dumps([reading()])}' + "}"}]}}]},
        {"usageMetadata": {"promptTokenCount": 31, "candidatesTokenCount": 9},
         "candidates": [{"finishReason": "STOP"}]},
    ]
    stream = "".join(f"data: {json.dumps(event)}\n\n" for event in events)
    request_count = 0
    def handler(request):
        nonlocal request_count
        request_count += 1
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=stream.encode())
    client = VisionClient(FOUNDRY_GEMINI, "token", httpx.MockTransport(handler))
    books = asyncio.run(client.read(Image.new("RGB", (10, 10)), "read", "tile-1"))
    assert books[0]["title"] == "Determined"
    assert client.calls[0]["usage"] == {"promptTokenCount": 31, "candidatesTokenCount": 9}
    assert request_count == 1


def test_provider_stream_errors_and_missing_finish_reason_fail():
    for content, expected in [
        ('data: {"error":{"message":"private provider text"}}\n\n', "reported an error"),
        ('data: {"modelVersion":"gemini-3.1-pro-preview","candidates":[{"content":{"parts":[{"text":"partial"}]}}]}\n\n', "before completion"),
    ]:
        client = VisionClient(
            FOUNDRY_GEMINI, "token",
            httpx.MockTransport(lambda request, content=content: httpx.Response(200, text=content)),
        )
        with pytest.raises(RecognitionError, match=expected) as exc:
            asyncio.run(client.read(Image.new("RGB", (10, 10)), "read", "tile-1"))
        assert "private provider text" not in str(exc.value)


def test_complete_harness_reads_verifies_maps_and_audits(monkeypatch, tmp_path):
    monkeypatch.setattr("server.recognition.RUNS_DIR", tmp_path)
    requests, events = [], []
    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        if len(requests) == 1:
            return response([reading()])
        # The independent request has no candidate titles from the first pass.
        text = body["contents"][0]["parts"][1]["text"]
        assert "Determined" not in text
        return response([reading(box={"top": .1, "left": .4, "width": .4, "height": .3})])
    async def emit(event):
        events.append(event)
    token = "ephemeral-test-token"
    books, metadata = asyncio.run(run_recognition(image_bytes(), FOUNDRY_GEMINI, emit, token, verify=True, transport=httpx.MockTransport(handler)))
    assert len(requests) == 2
    assert books[0]["verification_status"] == "verified"
    assert books[0]["box"] == pytest.approx(reading()["box"])
    assert metadata["mode"] == "live"
    assert metadata["tokens_used"] == 254
    assert metadata["harness"]["calls_completed"] == 2
    assert metadata["harness"]["measured_accuracy"] is None
    audit_text = (tmp_path / f"{metadata['run_id']}.json").read_text()
    audit = json.loads(audit_text)
    assert audit["status"] == "complete"
    assert token not in audit_text
    assert "base64" not in audit_text
    assert audit["calls"][0]["actual_model"] == FOUNDRY_GEMINI.model_id
    assert [e["status"] for e in events] == ["preparing", "reading", "reading", "verifying", "verifying"]
    assert events[0]["total_calls"] == 2
    assert events[0]["completed_calls"] == 0
    assert events[-1]["completed_calls"] == 2


def test_same_photo_retry_starts_a_fresh_scan(monkeypatch, tmp_path):
    monkeypatch.setattr("server.recognition.RUNS_DIR", tmp_path)
    requests, first_events, retry_events = [], [], []

    def handler(request):
        requests.append(request)
        return response([reading()])

    async def emit_first(event):
        first_events.append(event)

    async def emit_retry(event):
        retry_events.append(event)

    raw = image_bytes()
    transport = httpx.MockTransport(handler)
    first_books, first_metadata = asyncio.run(
        run_recognition(raw, FOUNDRY_GEMINI, emit_first, "test-token", verify=True, transport=transport)
    )
    retry_books, retry_metadata = asyncio.run(
        run_recognition(raw, FOUNDRY_GEMINI, emit_retry, "test-token", verify=True, transport=transport)
    )

    assert first_books == retry_books
    assert len(requests) == 4
    assert first_metadata["harness"]["model_requests_made"] == 2
    assert retry_metadata["harness"]["model_requests_made"] == 2
    assert [event["status"] for event in retry_events] == ["preparing", "reading", "reading", "verifying", "verifying"]
    assert retry_events[0]["total_calls"] == 2
    assert retry_events[0]["completed_calls"] == 0
    assert retry_events[-1]["completed_calls"] == 2


def test_output_limited_verification_splits_and_retry_starts_from_first_tile(monkeypatch, tmp_path):
    monkeypatch.setattr("server.recognition.RUNS_DIR", tmp_path)
    requests, first_events, retry_events = [], [], []

    def handler(request):
        body = json.loads(request.content)
        image = Image.open(io.BytesIO(base64.b64decode(body["contents"][0]["parts"][0]["inlineData"]["data"])))
        requests.append(image.size)
        if len(requests) == 2:
            return response([], complete=False)
        return response([reading()])

    async def emit_first(event):
        first_events.append(event)

    async def emit_retry(event):
        retry_events.append(event)

    raw = image_bytes()
    transport = httpx.MockTransport(handler)
    books, first_metadata = asyncio.run(
        run_recognition(raw, FOUNDRY_GEMINI, emit_first, "test-token", verify=True, transport=transport)
    )
    request_count_after_first = len(requests)
    retry_books, retry_metadata = asyncio.run(
        run_recognition(raw, FOUNDRY_GEMINI, emit_retry, "test-token", verify=True, transport=transport)
    )

    assert request_count_after_first == 6
    assert len(requests) == request_count_after_first + 2
    assert first_metadata["harness"]["model_requests_made"] == 6
    assert retry_metadata["harness"]["model_requests_made"] == 2
    assert [book["title"] for book in retry_books] == [book["title"] for book in books]
    assert any(event["status"] == "splitting" for event in first_events)
    assert not any(event["status"] == "splitting" for event in retry_events)
    assert requests[request_count_after_first:] == [(100, 50), (50, 100)]
    assert retry_events[0]["total_calls"] == 2


def test_interrupted_split_retry_starts_over_from_first_tile(monkeypatch, tmp_path):
    monkeypatch.setattr("server.recognition.RUNS_DIR", tmp_path)
    requests = []

    def handler(_request):
        requests.append(None)
        if len(requests) in (2, 6):
            if len(requests) == 2:
                return response([], complete=False)
            raise httpx.ConnectError("simulated connection loss")
        return response([reading()])

    async def emit(_event):
        return None

    raw = image_bytes()
    transport = httpx.MockTransport(handler)
    with pytest.raises(RecognitionError, match="could not be reached"):
        asyncio.run(run_recognition(raw, FOUNDRY_GEMINI, emit, "test-token", verify=True, transport=transport))

    failed_audit = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    assert failed_audit["status"] == "failed_or_cancelled"
    assert failed_audit["failure"]["code"] == "inference"
    assert len(failed_audit["calls"]) == 5

    books, metadata = asyncio.run(
        run_recognition(raw, FOUNDRY_GEMINI, emit, "test-token", verify=True, transport=transport)
    )

    assert books
    assert len(requests) == 8
    assert metadata["harness"]["model_requests_made"] == 2
    assert all("reused_from_run_id" not in call for call in failed_audit["calls"])


def test_invalid_boxes_retain_titles_without_wasting_extra_model_requests(monkeypatch, tmp_path):
    monkeypatch.setattr("server.recognition.RUNS_DIR", tmp_path)
    requests, events = [], []

    def handler(_request):
        requests.append(None)
        if len(requests) == 1:
            return response([reading(box={"top": .8, "left": .1, "width": .3, "height": .3})])
        return response([reading()])

    async def emit(event):
        events.append(event)

    books, metadata = asyncio.run(
        run_recognition(
            image_bytes(), FOUNDRY_GEMINI, emit, "test-token",
            verify=True, transport=httpx.MockTransport(handler),
        )
    )

    assert books
    assert len(requests) == 2
    assert metadata["harness"]["model_requests_made"] == 2
    assert metadata["harness"]["unlocated_readings"] == 1
    assert books[0]["title_status"] == "agreed"
    assert books[0]["position_status"] == "needs_review"
    assert not any(event["status"] == "splitting" for event in events)


def test_output_limited_reading_recursively_splits_and_retry_starts_over(monkeypatch, tmp_path):
    monkeypatch.setattr("server.recognition.RUNS_DIR", tmp_path)
    requests = []

    def handler(_request):
        requests.append(None)
        if len(requests) in (1, 3):
            return response([], complete=False)
        return response([reading()])

    async def emit(_event):
        return None

    raw = image_bytes()
    transport = httpx.MockTransport(handler)
    books, metadata = asyncio.run(
        run_recognition(raw, FOUNDRY_GEMINI, emit, "test-token", verify=True, transport=transport)
    )
    retry_books, retry_metadata = asyncio.run(
        run_recognition(raw, FOUNDRY_GEMINI, emit, "test-token", verify=True, transport=transport)
    )

    assert books
    assert [book["title"] for book in retry_books] == [book["title"] for book in books]
    assert len(requests) == 12
    assert metadata["harness"]["model_requests_made"] == 10
    assert retry_metadata["harness"]["model_requests_made"] == 2


def test_retries_always_make_new_requests_for_each_photo(monkeypatch, tmp_path):
    monkeypatch.setattr("server.recognition.RUNS_DIR", tmp_path)
    requests = []

    def handler(request):
        requests.append(request)
        return response([reading()])

    async def emit(_event):
        return None

    transport = httpx.MockTransport(handler)
    asyncio.run(run_recognition(image_bytes(), FOUNDRY_GEMINI, emit, "test-token", verify=True, transport=transport))
    _, metadata = asyncio.run(
        run_recognition(image_bytes((101, 50)), FOUNDRY_GEMINI, emit, "test-token", verify=True, transport=transport)
    )

    assert len(requests) == 4
    assert metadata["harness"]["model_requests_made"] == 2


def test_failure_is_audited_and_never_returns_replay(monkeypatch, tmp_path):
    monkeypatch.setattr("server.recognition.RUNS_DIR", tmp_path)
    async def emit(event):
        pass
    with pytest.raises(RecognitionError):
        asyncio.run(run_recognition(image_bytes(), FOUNDRY_GEMINI, emit, "test-token", verify=True, transport=httpx.MockTransport(lambda request: httpx.Response(403))))
    files = list(tmp_path.glob("*.json"))
    assert len(files) == 1
    assert json.loads(files[0].read_text())["status"] == "failed_or_cancelled"


@pytest.mark.parametrize("verify_box", [None, {"top": .8, "left": .8, "width": .1, "height": .1}])
def test_correct_title_survives_unconfirmed_location_and_is_not_also_missing(verify_box):
    store, bay = tiny_store()
    merged = merge_readings([obs(), obs("verify", box=verify_box)])
    assert merged[0]["title_status"] == "agreed"
    assert merged[0]["position_status"] == "needs_review"
    result = compare_books(store, bay, merged)
    assert result["shelf_items"][0]["status"] == "matched"
    assert result["shelf_items"][0]["sku"] == "a"
    assert result["metrics"]["matched_count"] == 1
    assert all(item["title"] != "Determined" for item in result["missing_items"])
    assert result["metrics"]["location_review_count"] == 1
    assert not any(task["type"] == "recognition_review" and task["title"] == "Determined" for task in result["action_tasks"])


def test_neighbouring_box_conflict_does_not_erase_agreed_title_identity():
    store, bay = tiny_store()
    merged = merge_readings([obs(), obs("verify"), obs("verify", title="Behave")])
    result = compare_books(store, bay, merged)
    determined = next(item for item in result["shelf_items"] if item["title"] == "Determined")
    assert determined["status"] == "matched"
    assert "overlapping_boxes" in determined["review_reasons"]
    assert determined["position_status"] == "needs_review"


def test_single_read_reserves_identity_but_does_not_confirm_stock_or_trigger_correction():
    store, bay = tiny_store()
    result = compare_books(store, bay, merge_readings([obs(title="Behave")]))
    item = result["shelf_items"][0]
    assert item["catalogue_status"] == "matched"
    assert item["status"] == "needs_review"
    assert not any(m["title"] == "Behave" for m in result["missing_items"])
    assert not any(t["type"] == "record_error" for t in result["action_tasks"])
    assert result["metrics"]["matched_count"] == 0


def test_inferred_full_title_never_becomes_confirmed_from_author_only_evidence():
    store, bay = tiny_store()
    book = Readings.model_validate({"books": [reading(visible_text="Robert Sapolsky")]}).books[0].model_dump()
    merged = merge_readings([{**book, "pass": phase, "tile_id": "tile-1"} for phase in ("read", "verify")])
    result = compare_books(store, bay, merged)
    assert result["shelf_items"] == []
    assert result["unresolved_readings"][0]["exclusion_reason"] == "uncertain_text"
    assert result["metrics"]["matched_count"] == 0


def test_screenshot_title_matches_f1_and_suggests_f1_when_m1_selected():
    store = json.loads((__import__('pathlib').Path(__file__).resolve().parents[1] / 'app/public/data/store.json').read_text())
    titles = ["Before I Go to Sleep", "Speaking for Myself", "Brilliance of the Moon"]
    books = [reading(title, verification_status="verified", title_status="agreed", position_status="needs_review", review_reasons=["position_unconfirmed"]) for title in titles]
    def compare(bay_id):
        return compare_books(store, next(b for b in store['bays'] if b['id'] == bay_id), books)
    wrong = compare('bay_m1')
    assert wrong['comparison_suggestion']['bay_id'] == 'bay_f1'
    assert all(item['status'] == 'misplaced' for item in wrong['shelf_items'])
    right = compare('bay_f1')
    assert right['comparison_suggestion'] is None
    assert all(item['status'] == 'matched' for item in right['shelf_items'])
    assert not set(titles) & {item['title'] for item in right['missing_items']}


def test_displayed_box_belongs_to_the_pair_that_confirmed_its_location():
    outlier = obs("verify", box={"top": .8, "left": .8, "width": .1, "height": .1})
    aligned = obs("verify")
    result = merge_readings([obs(), outlier, aligned])[0]
    assert result['position_status'] == 'agreed'
    assert result['box'] == aligned['box']
    assert result['box'] != outlier['box']
