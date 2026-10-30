"""build_store.py: Generate deterministic simulated store data for Shelf Check demo.

Generates:
- app/public/data/store.json: Store metadata, scannable and context bays, catalogue, inventory, planogram
- pipeline/planted.json: Ground-truth record of planted exceptions (phantom, record error, misplaced)
"""
import json
import hashlib
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GT_PATH = ROOT / "pipeline" / "demo_books.json"
STORE_OUT = ROOT / "app" / "public" / "data" / "store.json"
PLANTED_OUT = ROOT / "pipeline" / "planted.json"

RANDOM_SEED = 42
random.seed(RANDOM_SEED)

# Map photos to bay IDs and descriptive names
BAY_PHOTO_MAP = {
    "f": {
        "id": "bay_f3",
        "code": "F3",
        "name": "Bay F3 · Fiction & Bestsellers",
        "photo": "f.jpg",
        "aisle": "F",
        "section": "Fiction & Bestsellers",
        "difficulty": "hard",
        "extra_out_of_stock": [
            {"title": "The Silent Patient", "author": "Alex Michaelides", "price": 17.99, "velocity": 2.8, "days_stockout": 4},
            {"title": "Where the Crawdads Sing", "author": "Delia Owens", "price": 18.00, "velocity": 1.9, "days_stockout": 3},
            {"title": "Tomorrow, and Tomorrow, and Tomorrow", "author": "Gabrielle Zevin", "price": 22.00, "velocity": 2.4, "days_stockout": 2},
        ],
        "phantom_titles": ["The Silent Patient", "Where the Crawdads Sing"],
        "record_error_title": "Atomic Habits",
        "misplaced_title": "The Magic of the Lost Earrings",  # On shelf f.jpg, belongs in Children's / YA (Bay C2 or K1)
        "misplaced_target_bay": "bay_c2",
        "misplaced_target_name": "Bay C2 · Illustrated & Children's",
    },
    "e": {
        "id": "bay_f1",
        "code": "F1",
        "name": "Bay F1 · General Fiction & Classics",
        "photo": "e.jpg",
        "aisle": "F",
        "section": "General Fiction & Classics",
        "difficulty": "hard",
        "extra_out_of_stock": [
            {"title": "The Midnight Library", "author": "Matt Haig", "price": 16.99, "velocity": 3.1, "days_stockout": 3},
            {"title": "Klara and the Sun", "author": "Kazuo Ishiguro", "price": 19.99, "velocity": 1.5, "days_stockout": 2},
            {"title": "A Gentleman in Moscow", "author": "Amor Towles", "price": 17.50, "velocity": 1.8, "days_stockout": 5},
        ],
        "phantom_titles": ["The Midnight Library"],
        "record_error_title": "The Giver of Stars",
        "misplaced_title": "Star Wars Episode V: The Empire Strikes Back",
        "misplaced_target_bay": "bay_d1",
        "misplaced_target_name": "Bay D1 · Sci-Fi & Media Arts",
    },
    "c": {
        "id": "bay_f2",
        "code": "F2",
        "name": "Bay F2 · Manga & Pop Culture",
        "photo": "c.png",
        "aisle": "F",
        "section": "Manga & Pop Culture",
        "difficulty": "medium",
        "extra_out_of_stock": [
            {"title": "Demon Slayer: Kimetsu no Yaiba, Vol. 1", "author": "Koyoharu Gotouge", "price": 11.99, "velocity": 3.5, "days_stockout": 2},
            {"title": "Chainsaw Man, Vol. 1", "author": "Tatsuki Fujimoto", "price": 11.99, "velocity": 2.9, "days_stockout": 3},
            {"title": "Jujutsu Kaisen, Vol. 1", "author": "Gege Akutami", "price": 11.99, "velocity": 3.2, "days_stockout": 4},
        ],
        "phantom_titles": ["Demon Slayer: Kimetsu no Yaiba, Vol. 1"],
        "record_error_title": "Attack on Titan: Omnibus (Volumes 1-2-3)",
        "misplaced_title": "The Disciplined Trader",  # Finance book sitting on manga shelf!
        "misplaced_target_bay": "bay_b1",
        "misplaced_target_name": "Bay B1 · Business & Finance",
    },
    "d": {
        "id": "bay_m1",
        "code": "M1",
        "name": "Bay M1 · Wellness & Modern Thought",
        "photo": "d.jpg",
        "aisle": "M",
        "section": "Wellness & Modern Thought",
        "difficulty": "medium",
        "extra_out_of_stock": [
            {"title": "Deep Work", "author": "Cal Newport", "price": 28.00, "velocity": 2.1, "days_stockout": 3},
            {"title": "Thinking, Fast and Slow", "author": "Daniel Kahneman", "price": 24.99, "velocity": 1.7, "days_stockout": 4},
            {"title": "Man's Search for Meaning", "author": "Viktor E. Frankl", "price": 15.99, "velocity": 2.5, "days_stockout": 2},
        ],
        "phantom_titles": ["Deep Work"],
        "record_error_title": "Fast Like a Girl",
        "misplaced_title": "Secret of the Nagas",  # Mythological fiction sitting in wellness!
        "misplaced_target_bay": "bay_b2",
        "misplaced_target_name": "Bay B2 · World Mythology & Fiction",
    },
    "a": {
        "id": "bay_a1",
        "code": "A1",
        "name": "Bay A1 · Art Theory & Philosophy",
        "photo": "a.jpg",
        "aisle": "A",
        "section": "Art Theory & Philosophy",
        "difficulty": "easy",
        "extra_out_of_stock": [
            {"title": "Ways of Seeing", "author": "John Berger", "price": 18.00, "velocity": 2.0, "days_stockout": 3},
            {"title": "Simulacra and Simulation", "author": "Jean Baudrillard", "price": 24.00, "velocity": 1.2, "days_stockout": 5},
            {"title": "The Medium is the Massage", "author": "Marshall McLuhan", "price": 19.50, "velocity": 1.4, "days_stockout": 4},
        ],
        "phantom_titles": ["Ways of Seeing"],
        "record_error_title": "Deconstruction: Theory and Practice",
        "misplaced_title": "Russische Avantgarde aus der Sammlung Costakis",
        "misplaced_target_bay": "bay_a3",
        "misplaced_target_name": "Bay A3 · Classical & Avant-Garde",
    },
    "b": {
        "id": "bay_a2",
        "code": "A2",
        "name": "Bay A2 · Classical Art & Renaissance",
        "photo": "b.jpg",
        "aisle": "A",
        "section": "Classical Art & Renaissance",
        "difficulty": "easy",
        "extra_out_of_stock": [
            {"title": "Lives of the Artists", "author": "Giorgio Vasari", "price": 22.50, "velocity": 1.3, "days_stockout": 4},
            {"title": "The Story of Art", "author": "E.H. Gombrich", "price": 39.95, "velocity": 2.1, "days_stockout": 2},
            {"title": "Leonardo da Vinci", "author": "Walter Isaacson", "price": 25.00, "velocity": 1.9, "days_stockout": 3},
        ],
        "phantom_titles": ["Lives of the Artists"],
        "record_error_title": "Art of the Renaissance",
        "misplaced_title": "Studies in Iconology",
        "misplaced_target_bay": "bay_a4",
        "misplaced_target_name": "Bay A4 · Cultural Studies & Iconography",
    },
}

# Context bays on floor plan (non-scannable in demo, to reflect a real 18-bay store layout)
CONTEXT_BAYS = [
    {"id": "bay_a3", "code": "A3", "name": "Bay A3 · Classical & Avant-Garde", "aisle": "A", "status": "healthy", "scanned_today": True, "open_exceptions": 0, "on_shelf_availability": 0.96},
    {"id": "bay_a4", "code": "A4", "name": "Bay A4 · Cultural Studies & Iconography", "aisle": "A", "status": "unscanned", "scanned_today": False, "open_exceptions": 0, "on_shelf_availability": 0.91},
    {"id": "bay_b1", "code": "B1", "name": "Bay B1 · Business & Finance", "aisle": "B", "status": "healthy", "scanned_today": True, "open_exceptions": 0, "on_shelf_availability": 0.95},
    {"id": "bay_b2", "code": "B2", "name": "Bay B2 · World Mythology & Fiction", "aisle": "B", "status": "healthy", "scanned_today": True, "open_exceptions": 0, "on_shelf_availability": 0.98},
    {"id": "bay_b3", "code": "B3", "name": "Bay B3 · Military & Ancient History", "aisle": "B", "status": "unscanned", "scanned_today": False, "open_exceptions": 0, "on_shelf_availability": 0.89},
    {"id": "bay_c1", "code": "C1", "name": "Bay C1 · Cooking & Wine", "aisle": "C", "status": "healthy", "scanned_today": True, "open_exceptions": 0, "on_shelf_availability": 0.97},
    {"id": "bay_c2", "code": "C2", "name": "Bay C2 · Illustrated & Children's", "aisle": "C", "status": "healthy", "scanned_today": True, "open_exceptions": 0, "on_shelf_availability": 0.94},
    {"id": "bay_d1", "code": "D1", "name": "Bay D1 · Sci-Fi & Media Arts", "aisle": "D", "status": "healthy", "scanned_today": True, "open_exceptions": 0, "on_shelf_availability": 0.95},
    {"id": "bay_d2", "code": "D2", "name": "Bay D2 · Nature & Environment", "aisle": "D", "status": "unscanned", "scanned_today": False, "open_exceptions": 0, "on_shelf_availability": 0.90},
    {"id": "bay_e1", "code": "E1", "name": "Bay E1 · Travel & Guides", "aisle": "E", "status": "healthy", "scanned_today": True, "open_exceptions": 0, "on_shelf_availability": 0.96},
    {"id": "bay_e2", "code": "E2", "name": "Bay E2 · Language & Reference", "aisle": "E", "status": "unscanned", "scanned_today": False, "open_exceptions": 0, "on_shelf_availability": 0.92},
    {"id": "bay_n1", "code": "N1", "name": "Bay N1 · Current Affairs & Essays", "aisle": "N", "status": "healthy", "scanned_today": True, "open_exceptions": 0, "on_shelf_availability": 0.97},
]


def build():
    random.seed(RANDOM_SEED)
    with open(GT_PATH, encoding="utf-8") as f:
        gt_data = json.load(f)

    planted_exceptions = []
    scannable_bays = []
    full_catalogue = {}
    store_inventory = {}

    for letter, bay_cfg in BAY_PHOTO_MAP.items():
        photo_key = bay_cfg["photo"]
        gt_entry = gt_data.get(photo_key)
        if not gt_entry:
            raise ValueError(f"Ground truth missing {photo_key}")

        bay_books = gt_entry["books"]
        bay_id = bay_cfg["id"]

        # Catalogue items for this bay
        catalogue_items = []
        shelf_titles = {b["title"] for b in bay_books}

        # 1. Add all ground-truth books that belong to this bay
        for b in bay_books:
            title = b["title"]
            author = b.get("author")
            price = round(random.uniform(14.0, 32.0), 2)
            velocity = round(random.uniform(0.6, 3.8), 1)

            # Determine simulated on-hand inventory
            if title == bay_cfg["record_error_title"]:
                # Record error: physically on shelf, system says 0!
                on_hand = 0
                system_status = "out_of_stock_in_system"
                planted_exceptions.append({
                    "bay_id": bay_id,
                    "bay_code": bay_cfg["code"],
                    "type": "record_error",
                    "title": title,
                    "author": author,
                    "system_on_hand": 0,
                    "actual_on_shelf": 1,
                    "price": price,
                    "velocity": velocity,
                    "action_required": "Correct inventory record to 1 (currently unorderable/unavailable online)",
                })
            elif title == bay_cfg.get("misplaced_title"):
                # Misplaced: physically on this shelf, but planogram assigns to another bay!
                on_hand = random.randint(1, 8)
                system_status = "misplaced"
                planted_exceptions.append({
                    "bay_id": bay_id,
                    "bay_code": bay_cfg["code"],
                    "type": "misplaced",
                    "title": title,
                    "author": author,
                    "assigned_bay_id": bay_cfg["misplaced_target_bay"],
                    "assigned_bay_name": bay_cfg["misplaced_target_name"],
                    "system_on_hand": on_hand,
                    "actual_on_shelf": 1,
                    "price": price,
                    "velocity": velocity,
                    "action_required": f"Relocate to {bay_cfg['misplaced_target_name']}",
                })
            else:
                # Normal healthy item on shelf
                on_hand = random.randint(1, 14)
                system_status = "in_stock"

            item = {
                "sku": f"SKU-{hashlib.sha256(f'{bay_id}:{title}'.encode()).hexdigest()[:12].upper()}",
                "title": title,
                "author": author,
                "assigned_bay_id": bay_cfg["misplaced_target_bay"] if title == bay_cfg.get("misplaced_title") else bay_id,
                "price": price,
                "sales_velocity_units_per_day": velocity,
                "simulated_on_hand": on_hand,
                "system_status": system_status,
                "physically_on_shelf": True,
            }
            catalogue_items.append(item)
            full_catalogue[item["sku"]] = item
            store_inventory[item["sku"]] = on_hand

        # 2. Add extra out-of-stock items (belong to bay, but not on shelf in photo)
        for oos in bay_cfg["extra_out_of_stock"]:
            title = oos["title"]
            author = oos["author"]
            price = oos["price"]
            velocity = oos["velocity"]
            days_stockout = oos["days_stockout"]

            if title in bay_cfg["phantom_titles"]:
                # Phantom inventory! System says in stock (e.g. 6), but empty shelf!
                on_hand = random.randint(4, 12)
                planted_exceptions.append({
                    "bay_id": bay_id,
                    "bay_code": bay_cfg["code"],
                    "type": "phantom_inventory",
                    "title": title,
                    "author": author,
                    "system_on_hand": on_hand,
                    "actual_on_shelf": 0,
                    "price": price,
                    "velocity": velocity,
                    "days_stockout": days_stockout,
                    "action_required": f"System shows {on_hand} in stock, none found on shelf. Check stockroom or reorder.",
                })
            else:
                # Real known out-of-stock: system on-hand is 0, correctly reordered
                on_hand = 0

            item = {
                "sku": f"SKU-{hashlib.sha256(f'{bay_id}:{title}'.encode()).hexdigest()[:12].upper()}",
                "title": title,
                "author": author,
                "assigned_bay_id": bay_id,
                "price": price,
                "sales_velocity_units_per_day": velocity,
                "simulated_on_hand": on_hand,
                "system_status": "phantom" if title in bay_cfg["phantom_titles"] else "out_of_stock",
                "physically_on_shelf": False,
                "days_since_stockout": days_stockout,
            }
            catalogue_items.append(item)
            full_catalogue[item["sku"]] = item
            store_inventory[item["sku"]] = on_hand

        # Compute initial bay metrics
        bay_exceptions = [e for e in planted_exceptions if e["bay_id"] == bay_id]

        scannable_bays.append({
            "id": bay_id,
            "code": bay_cfg["code"],
            "name": bay_cfg["name"],
            "photo": bay_cfg["photo"],
            "aisle": bay_cfg["aisle"],
            "section": bay_cfg["section"],
            "difficulty": bay_cfg["difficulty"],
            "scannable": True,
            "status": "action_needed" if bay_exceptions else "healthy",
            "scanned_today": True,
            "last_scanned_at": "Today 08:30 AM",
            "open_exceptions": len(bay_exceptions),
            "expected_items_count": len(catalogue_items),
            "ground_truth_items_count": len(bay_books),
            "catalogue_skus": [item["sku"] for item in catalogue_items],
        })

    # Combine all bays
    all_bays = scannable_bays + CONTEXT_BAYS
    for bay in all_bays:
        assigned = [item for item in full_catalogue.values() if item["assigned_bay_id"] == bay["id"]]
        bay["catalogue_skus"] = [item["sku"] for item in assigned]
        bay["expected_items_count"] = len(assigned)

    store_data = {
        "store_name": "Straive Demo Bookstore",
        "store_id": "STORE-842",
        "description": "Simulated store environment modeled after real retail shelf operations.",
        "disclaimer": "Simulated store data",
        "total_bays": len(all_bays),
        "scannable_bays_count": len(scannable_bays),
        "bays": all_bays,
        "catalogue": full_catalogue,
        "initial_inventory": store_inventory,
        "summary": {
            "on_shelf_availability_pct": 91.4,
            "open_exceptions_total": sum(b["open_exceptions"] for b in all_bays),
            "bays_scanned_today": sum(1 for b in all_bays if b.get("scanned_today")),
        }
    }

    STORE_OUT.parent.mkdir(parents=True, exist_ok=True)
    PLANTED_OUT.parent.mkdir(parents=True, exist_ok=True)

    with open(STORE_OUT, "w", encoding="utf-8") as f:
        json.dump(store_data, f, indent=2, ensure_ascii=False)

    with open(PLANTED_OUT, "w", encoding="utf-8") as f:
        json.dump({"planted_exceptions": planted_exceptions, "count": len(planted_exceptions)}, f, indent=2, ensure_ascii=False)

    print(f"Wrote {STORE_OUT} ({len(all_bays)} bays, {len(full_catalogue)} catalogue items)")
    print(f"Wrote {PLANTED_OUT} ({len(planted_exceptions)} planted exceptions across 6 scannable bays)")


if __name__ == "__main__":
    build()
