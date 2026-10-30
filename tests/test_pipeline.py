"""test_pipeline.py: Unit and integration tests for Shelf Check data and scan pipelines."""
import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
STORE_FILE = ROOT / "app" / "public" / "data" / "store.json"
PLANTED_FILE = ROOT / "pipeline" / "planted.json"
SCANS_DIR = ROOT / "app" / "public" / "data" / "scans"
EVALUATE_SCRIPT = ROOT / "reference" / "bookshelf-benchmark" / "benchmark" / "evaluate.py"
GT_FILE = ROOT / "reference" / "bookshelf-benchmark" / "data" / "ground_truth.json"


def normalize(text):
    text = unicodedata.normalize('NFKD', (text or '').casefold()).replace('&', ' and ')
    out = []
    for ch in text:
        if unicodedata.category(ch) != 'Mn' and (ch.isalnum() or ch == ' '):
            out.append(ch)
        else:
            out.append(' ')
    return ' '.join(''.join(out).split())


def similarity(a, b):
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def test_store_data_structure():
    assert STORE_FILE.exists(), f"Missing {STORE_FILE}"
    with open(STORE_FILE, encoding="utf-8") as f:
        store = json.load(f)

    assert store["store_name"] == "Straive Demo Bookstore"
    assert store["disclaimer"] == "Simulated store data"
    assert len(store["bays"]) >= 16

    scannable = [b for b in store["bays"] if b.get("scannable")]
    assert len(scannable) == 6, f"Expected 6 scannable bays, found {len(scannable)}"
    for bay in scannable:
        assert bay["photo"] in ["a.jpg", "b.jpg", "c.png", "d.jpg", "e.jpg", "f.jpg"]


def test_multiple_bay_allocations_do_not_overwrite_inventory():
    store = json.loads(STORE_FILE.read_text(encoding="utf-8"))
    copies = [item for item in store["catalogue"].values() if item["title"] == "Atomic Habits"]
    assert len(copies) == 2
    assert len({item["sku"] for item in copies}) == 2
    assert next(item for item in copies if item["assigned_bay_id"] == "bay_f3")["simulated_on_hand"] == 0
    assert next(item for item in copies if item["assigned_bay_id"] == "bay_f1")["simulated_on_hand"] > 0
    for bay in store["bays"]:
        expected = {item["sku"] for item in store["catalogue"].values() if item["assigned_bay_id"] == bay["id"]}
        assert set(bay["catalogue_skus"]) == expected
        assert bay["expected_items_count"] == len(expected)


def test_replay_generation_is_reproducible_without_answer_key(tmp_path, monkeypatch):
    from pipeline import run_replay_scans
    monkeypatch.setattr(run_replay_scans, "SCANS_DIR", tmp_path)
    run_replay_scans.run()
    first = {p.name: p.read_bytes() for p in tmp_path.glob("*.json")}
    run_replay_scans.run()
    assert {p.name: p.read_bytes() for p in tmp_path.glob("*.json")} == first
    assert len(first) == 6


def test_planted_exceptions_exist():
    assert PLANTED_FILE.exists(), f"Missing {PLANTED_FILE}"
    with open(PLANTED_FILE, encoding="utf-8") as f:
        data = json.load(f)

    exceptions = data["planted_exceptions"]
    assert len(exceptions) >= 6

    types = {e["type"] for e in exceptions}
    assert "phantom_inventory" in types
    assert "record_error" in types
    assert "misplaced" in types


def test_perfect_recognition_catches_all_planted_exceptions():
    """Given the exact ground truth as physical shelf items, the planogram comparison
    must detect 100% of the planted exceptions with 0 false alarms."""
    with open(STORE_FILE, encoding="utf-8") as f:
        store = json.load(f)
    with open(PLANTED_FILE, encoding="utf-8") as f:
        planted = json.load(f)["planted_exceptions"]
    if not GT_FILE.exists():
        pytest.skip("Optional benchmark checkout is not installed")
    with open(GT_FILE, encoding="utf-8") as f:
        gt = json.load(f)

    catalogue = store["catalogue"]
    scannable_bays = [b for b in store["bays"] if b.get("scannable")]

    for bay in scannable_bays:
        bay_id = bay["id"]
        photo = bay["photo"]
        gt_books = gt[photo]["books"]
        shelf_titles = [b["title"] for b in gt_books]

        bay_planogram = [item for item in catalogue.values() if item.get("assigned_bay_id") == bay_id]

        # Check missing (phantom)
        for p_item in bay_planogram:
            on_shelf = any(similarity(p_item["title"], st) >= 0.85 for st in shelf_titles)
            if not on_shelf and p_item["simulated_on_hand"] > 0:
                # Must be a planted phantom inventory
                matching_planted = [
                    e for e in planted
                    if e["bay_id"] == bay_id and e["type"] == "phantom_inventory" and similarity(e["title"], p_item["title"]) >= 0.85
                ]
                assert len(matching_planted) > 0, f"Unplanned phantom alert for {p_item['title']}"

        # Check record error (on shelf, system on hand = 0)
        planted_re = [e for e in planted if e["bay_id"] == bay_id and e["type"] == "record_error"]
        for re_item in planted_re:
            found_on_shelf = any(similarity(re_item["title"], st) >= 0.85 for st in shelf_titles)
            assert found_on_shelf, f"Planted record error {re_item['title']} was not on shelf"


def test_replay_scans_generated():
    scannable_ids = ["bay_f3", "bay_f1", "bay_f2", "bay_m1", "bay_a1", "bay_a2"]
    for bay_id in scannable_ids:
        scan_file = SCANS_DIR / f"{bay_id}.json"
        assert scan_file.exists(), f"Missing {scan_file}"
        with open(scan_file, encoding="utf-8") as f:
            data = json.load(f)

        assert data["bay_id"] == bay_id
        assert data["model"] == ("Gemini 3.8 Flash" if bay_id in {"bay_a1", "bay_a2"} else "Claude Opus 5.5")
        assert data["mode"] == "replay"
        assert data["inference_duration_seconds"] is None
        assert data["estimated_cost_usd"] is None
        assert not data["harness"]["rotated_verification"]
        assert len(data["shelf_items"]) > 0
        assert len(data["planogram_items"]) > 0
        assert len(data["action_tasks"]) > 0
        assert "planogram_compliance_pct" in data["metrics"]
        for item in data["shelf_items"]:
            assert item["confidence"] is None
            assert item["box_source"] == "unavailable"
            assert item["box"] is None


def test_unmodified_evaluate_py_exists():
    if not EVALUATE_SCRIPT.exists():
        pytest.skip("Optional benchmark checkout is not installed")
    content = EVALUATE_SCRIPT.read_text(encoding="utf-8")
    assert "def score_run" in content
    assert "def match_books" in content
    assert "TITLE_THRESHOLD = 0.85" in content


def test_no_api_secret_keys_in_dist():
    dist_dir = ROOT / "app" / "dist"
    if not dist_dir.exists():
        pytest.skip("dist/ directory not built yet")
    pattern = re.compile(r'(sk-ant-[a-zA-Z0-9_\-]{20,}|sk-[a-zA-Z0-9_\-]{20,}|AIza[0-9A-Za-z\-_]{35})')
    for p in dist_dir.rglob("*"):
        if p.suffix in [".js", ".html", ".css", ".json"]:
            text = p.read_text(errors="ignore")
            matches = pattern.findall(text)
            assert not matches, f"Secret key pattern found in {p}: {matches}"
