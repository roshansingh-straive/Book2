"""Compare lower-cost vision models on the demo's actual bookshelf image tiles.

This is a separate opt-in benchmark. Without --run, it only prints the plan.
No access token, image data, or request headers are written to a report.
"""
from __future__ import annotations

import argparse
import csv
import getpass
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server.recognition import (PROMPT, encode_image, load_image, parse_readings,
                                provider_schema, tile_image)
from server.text import title_key

PHOTOS = ("a.jpg", "b.jpg", "c.png", "d.jpg", "e.jpg", "f.jpg")
PILOT = ("a.jpg", "c.png", "f.jpg")
BASE_URL = "https://llmfoundry.straivedemo.com"
PROJECT = "llmproxy-playground"
MODEL_SPECS = {
    "gemini": {"id": "gemini-3-flash-preview", "provider": "gemini", "input": 0.50, "output": 3.00},
    "pro": {"id": "gemini-3.1-pro-preview", "provider": "gemini", "input": 2.00, "output": 12.00},
    "gpt": {"id": "gpt-5-mini", "provider": "openai", "input": 0.25, "output": 2.00},
    "claude": {"id": "claude-3-haiku-20240307", "provider": "anthropic", "input": 0.25, "output": 1.25},
    "llama": {"id": "meta-llama/llama-4-scout", "provider": "openrouter", "input": 0.08, "output": 0.30},
}
# Internal Foundry rates supplied for this comparison; not necessarily public rates.


def request_parts(key: str, image_b64: str, base_url: str, max_tokens: int):
    """Return the provider-native Foundry endpoint and request body."""
    spec = MODEL_SPECS[key]
    model = spec["id"]
    base = base_url.rstrip("/")
    if key in ("gemini", "pro"):
        return (f"{base}/gemini/v1beta/models/{model}:streamGenerateContent?alt=sse", {
            "contents": [{"role": "user", "parts": [
                {"inlineData": {"mimeType": "image/png", "data": image_b64}},
                {"text": PROMPT},
            ]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": provider_schema(),
                "maxOutputTokens": max_tokens,
                "thinkingConfig": {"thinkingLevel": "HIGH" if key == "pro" else "LOW"},
            },
        })
    if key == "claude":
        return (f"{base}/anthropic/v1/messages", {
            "model": model,
            "max_tokens": min(max_tokens, 4096),
            "messages": [{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_b64}},
                {"type": "text", "text": PROMPT},
            ]}],
        })
    body = {
        "model": model,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": PROMPT},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64," + image_b64}},
        ]}],
        "response_format": {"type": "json_object"},
    }
    if key == "gpt":
        body["reasoning_effort"] = "low"
        body["max_completion_tokens"] = max_tokens
    else:
        body["max_tokens"] = max_tokens
    return f"{base}/{spec['provider']}/v1/chat/completions", body


def parse_sse(lines):
    """Collect Gemini SSE chunks, including completion status and token usage."""
    text_parts, usage, model, finish, data_lines = [], {}, None, None, []

    def consume():
        nonlocal model, finish
        if not data_lines:
            return
        raw = "\n".join(data_lines)
        data_lines.clear()
        if raw == "[DONE]":
            return
        event = json.loads(raw)
        if "error" in event:
            raise ValueError("provider_stream_error")
        model = event.get("modelVersion") or model
        usage.update(event.get("usageMetadata") or {})
        for candidate in event.get("candidates", []):
            finish = candidate.get("finishReason") or finish
            for part in candidate.get("content", {}).get("parts", []):
                if part.get("text") and not part.get("thought"):
                    text_parts.append(part["text"])

    for line in lines:
        if not line:
            consume()
        elif line.startswith("data:"):
            data_lines.append(line[5:].strip())
    consume()
    if finish != "STOP":
        raise ValueError("incomplete_model_response_" + str(finish))
    return "".join(text_parts), usage, model


def call_model(client, key, encoded, token, base_url, max_tokens):
    endpoint, body = request_parts(key, encoded, base_url, max_tokens)
    headers = {"Authorization": f"Bearer {token}:{PROJECT}", "Content-Type": "application/json"}
    if key == "claude":
        headers["anthropic-version"] = "2023-06-01"
    with client.stream("POST", endpoint, headers=headers, json=body) as response:
        if response.status_code >= 400:
            raise RuntimeError("http_" + str(response.status_code))
        if key in ("gemini", "pro"):
            text, usage, returned_model = parse_sse(response.iter_lines())
            tokens_in = usage.get("promptTokenCount")
            candidates = usage.get("candidatesTokenCount")
            thoughts = usage.get("thoughtsTokenCount", 0)
            tokens_out = candidates + thoughts if isinstance(candidates, int) else None
        else:
            data = response.read()
            result = json.loads(data)
            if key == "claude":
                if result.get("stop_reason") not in ("end_turn", "stop_sequence"):
                    raise ValueError("incomplete_model_response_" + str(result.get("stop_reason")))
                text = "".join(part.get("text", "") for part in result["content"] if part.get("type") == "text")
                usage = result.get("usage") or {}
                returned_model = result.get("model")
                tokens_in = usage.get("input_tokens")
                tokens_out = usage.get("output_tokens")
                return json.loads(text.strip().removeprefix("```json").removesuffix("```").strip()), returned_model, tokens_in, tokens_out
            choice = result["choices"][0]
            if choice.get("finish_reason") not in (None, "stop"):
                raise ValueError("incomplete_model_response_" + str(choice.get("finish_reason")))
            text = choice["message"]["content"]
            if not isinstance(text, str):
                raise ValueError("missing_text_content")
            usage = result.get("usage") or {}
            returned_model = result.get("model")
            tokens_in = usage.get("prompt_tokens")
            tokens_out = usage.get("completion_tokens")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("empty_model_response")
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    return json.loads(cleaned), returned_model, tokens_in, tokens_out


def cost_usd(key, tokens_in, tokens_out):
    if not isinstance(tokens_in, int) or not isinstance(tokens_out, int):
        return None
    spec = MODEL_SPECS[key]
    return round((tokens_in * spec["input"] + tokens_out * spec["output"]) / 1_000_000, 7)


def reference_keys(reference, photo):
    return {title_key(item["title"]) for item in reference[photo]["books"] if title_key(item["title"])}


def summarize(rows, reference, counts, cropped):
    output = []
    for photo in counts:
        wanted = reference_keys(reference, photo)
        for model in MODEL_SPECS:
            subset = [row for row in rows if row["image"] == photo and row["model_key"] == model]
            if not subset:
                continue
            recognized = {title_key(book["title"]) for row in subset for book in row["readings"]
                          if title_key(book["title"])}
            matched = len(wanted & recognized)
            succeeded = sum(row["status"] == "ok" for row in subset)
            complete = (not cropped and len(subset) == counts[photo] and succeeded == len(subset))
            usage_complete = complete and all(row["estimated_cost_usd"] is not None for row in subset)
            output.append({
                "image": photo, "model": MODEL_SPECS[model]["id"],
                "planned_tiles": counts[photo], "attempted_calls": len(subset),
                "successful_calls": succeeded, "failed_calls": len(subset) - succeeded,
                "unique_titles": len(recognized), "reference_title_overlap": matched,
                "reference_titles": len(wanted),
                "reference_overlap_pct_proxy": round(100 * matched / len(wanted), 1) if complete and wanted else None,
                "quality_status": "complete_unverified" if complete else "partial_or_failed",
                "total_duration_seconds": round(sum(row["duration_seconds"] for row in subset), 2),
                "input_tokens": sum(row["input_tokens"] for row in subset) if usage_complete else None,
                "output_tokens": sum(row["output_tokens"] for row in subset) if usage_complete else None,
                "estimated_cost_usd": round(sum(row["estimated_cost_usd"] for row in subset), 7) if usage_complete else None,
            })
    return output


def save_reports(directory, rows, summary, metadata):
    directory.mkdir(parents=True, exist_ok=True)
    full = {"metadata": metadata, "summary": summary, "calls": rows}
    temp = directory / "results.json.tmp"
    temp.write_text(json.dumps(full, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(directory / "results.json")
    if summary:
        with (directory / "summary.csv").open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(summary[0]))
            writer.writeheader()
            writer.writerows(summary)


def save_static_results(path, run_name, rows, summary, metadata):
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"runs": [{"name": run_name, "metadata": metadata,
                         "summary": summary, "calls": rows}]}
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Explicitly permit live, potentially billable model requests")
    parser.add_argument("--all-images", action="store_true", help="Use all six sample photos instead of the 3-image pilot")
    parser.add_argument("--images", nargs="+", choices=PHOTOS, default=list(PILOT))
    parser.add_argument("--models", nargs="+", choices=tuple(MODEL_SPECS), default=["gemini", "gpt", "claude"])
    parser.add_argument("--max-tiles", type=int, default=0, help="Optional per-image limit for a cheaper smoke test")
    parser.add_argument("--max-output-tokens", type=int, default=8192)
    parser.add_argument("--base-url", default=BASE_URL, help="Company gateway origin, not a third-party API host")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "qa" / "model_comparison_results")
    args = parser.parse_args(argv)
    if args.max_tiles < 0 or args.max_output_tokens < 256:
        parser.error("max-tiles must be nonnegative and max-output-tokens must be at least 256")
    photos = list(PHOTOS) if args.all_images else list(dict.fromkeys(args.images))
    models = list(dict.fromkeys(args.models))
    counts = {}
    for photo in photos:
        image = load_image((ROOT / "app" / "public" / "photos" / photo).read_bytes())
        counts[photo] = len(tile_image(image.size))
        image.close()
    print("Shelf Check vision model comparison")
    for photo in photos:
        selected = min(counts[photo], args.max_tiles) if args.max_tiles else counts[photo]
        print(f"  {photo}: {counts[photo]} native-resolution tiles; selected {selected}")
    total = sum(min(n, args.max_tiles) if args.max_tiles else n for n in counts.values()) * len(models)
    print("Models:", ", ".join(MODEL_SPECS[x]["id"] for x in models))
    print(f"Planned paid/chargeable calls if run: {total}")
    print("Illustrative token prices use the internal rates supplied, NOT measured image costs.")
    if not args.run:
        print("DRY RUN ONLY: no model API calls made. Add --run to perform the comparison.")
        return 0
    token = os.environ.get("LLMFOUNDRY_TOKEN", "").strip()
    if not token:
        token = getpass.getpass("Straive Foundry token (hidden; never saved): ").strip()
    if not token or "\n" in token or "\r" in token:
        print("No usable token. No requests made.")
        return 2

    reference = json.loads((ROOT / "pipeline" / "demo_books.json").read_text(encoding="utf-8"))
    run_name = datetime.now(timezone.utc).strftime("run_%Y%m%dT%H%M%SZ")
    directory = args.output_dir / run_name
    rows = []
    blocked = set()
    metadata = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "photos": photos, "model_keys": models, "gateway": args.base_url,
        "max_tiles": args.max_tiles, "max_output_tokens": args.max_output_tokens,
        "prompt": "server.recognition.PROMPT",
        "note": "Reference overlap is NOT verified precision/recall; manually review image evidence.",
    }
    timeout = httpx.Timeout(240, connect=15, write=120, pool=30)
    with httpx.Client(timeout=timeout, follow_redirects=False, transport=httpx.HTTPTransport(retries=0)) as client:
        for photo in photos:
            image = load_image((ROOT / "app" / "public" / "photos" / photo).read_bytes())
            tiles = tile_image(image.size)
            selected_tiles = tiles[:args.max_tiles] if args.max_tiles else tiles
            for key in models:
                if key in blocked:
                    print(f"  Skipping {key}: prior auth/route error.")
                    continue
                for index, tile in enumerate(selected_tiles, 1):
                    started = time.monotonic()
                    row = {"image": photo, "model_key": key, "model": MODEL_SPECS[key]["id"],
                           "tile_id": tile.id, "bounds": tile.bounds, "status": "error",
                           "error": None, "returned_model": None, "readings": [],
                           "rejected_readings": 0, "input_tokens": None, "output_tokens": None,
                           "estimated_cost_usd": None}
                    try:
                        with image.crop(tile.bounds) as crop:
                            encoded = encode_image(crop)
                            image_size = crop.size
                        payload, returned, tokens_in, tokens_out = call_model(
                            client, key, encoded, token, args.base_url, args.max_output_tokens
                        )
                        row.update(returned_model=returned, input_tokens=tokens_in,
                                   output_tokens=tokens_out, estimated_cost_usd=cost_usd(key, tokens_in, tokens_out))
                        parsed, rejected = parse_readings(payload, image_size)
                        row.update(status="ok", rejected_readings=rejected,
                                   readings=[reading.model_dump() for reading in parsed.books])
                    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError, RuntimeError) as error:
                        # Never persist provider error bodies (they can include sensitive data).
                        code = str(error) if str(error).startswith(("http_", "incomplete_", "empty_", "missing_", "provider_")) else type(error).__name__
                        row["error"] = code
                        if code in {"http_401", "http_403", "http_404"}:
                            blocked.add(key)
                    row["duration_seconds"] = round(time.monotonic() - started, 2)
                    rows.append(row)
                    status = row["status"] if row["status"] == "ok" else "ERROR " + (row["error"] or "")
                    print(f"  {photo} {key} {index}/{len(selected_tiles)}: {status}; "
                          f"{len(row['readings'])} readings, {row['duration_seconds']}s", flush=True)
                    save_reports(directory, rows, summarize(rows, reference, counts, bool(args.max_tiles)), metadata)
            image.close()
    print("Reports saved:", directory)
    save_static_results(ROOT / "app" / "public" / "data" / "model_comparison_results.json",
                        run_name, rows, summarize(rows, reference, counts, bool(args.max_tiles)), metadata)
    print("Static results saved: app/public/data/model_comparison_results.json")
    print("No human-verified ground truth exists in this folder; reference overlap is only a proxy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
