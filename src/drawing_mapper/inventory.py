from __future__ import annotations

import csv
import json
import re
from pathlib import Path


FLOOR_PATTERNS = [
    (re.compile(r"지하\s*(\d+)\s*층"), lambda match: f"B{match.group(1)}"),
    (re.compile(r"地下\s*(\d+)\s*층"), lambda match: f"B{match.group(1)}"),
    (re.compile(r"B\s*(\d+)\s*F?", re.IGNORECASE), lambda match: f"B{match.group(1)}"),
    (re.compile(r"지상\s*(\d+)\s*층"), lambda match: f"{match.group(1)}F"),
    (re.compile(r"(\d+)\s*층"), lambda match: f"{match.group(1)}F"),
    (re.compile(r"(\d+)\s*F", re.IGNORECASE), lambda match: f"{match.group(1)}F"),
    (re.compile(r"ROOF|옥상", re.IGNORECASE), lambda match: "ROOF"),
]

DISCIPLINE_KEYWORDS = {
    "mechanical": [
        "기계",
        "공조",
        "배관",
        "냉동",
        "냉수",
        "팬",
        "AHU",
        "FCU",
        "PUMP",
        "펌프",
        "보일러",
    ],
    "electrical": [
        "전기",
        "동력",
        "전력",
        "간선",
        "케이블",
        "UPS",
        "분전",
        "수배전",
        "발전기",
        "단선",
    ],
    "telecom": ["통신", "CCTV", "제어", "BMS", "DCIM", "네트워크", "LAN"],
    "fire": ["소방", "스프링클러", "SPRINKLER", "SP", "화재", "감지"],
    "plumbing": ["위생", "급수", "배수", "오수", "우수", "DRAIN", "WATER"],
    "architecture": ["건축", "평면", "입면", "단면", "확대평면", "창호"],
}


def build_dwg_inventory(
    metadata_path: Path,
    raw_dir: Path,
    output_dir: Path,
    allowed_floor_levels: list[int] | None = None,
) -> list[dict]:
    output_dir.mkdir(parents=True, exist_ok=True)
    drive_files = _load_drive_files(metadata_path)
    local_files = _index_local_dwg_files(raw_dir, [file.get("id", "") for file in drive_files])

    # Inventory connects Drive metadata to local files and adds rough hints that
    # later steps use for conversion priority and candidate grouping.
    inventory = []
    for file in drive_files:
        file_id = file.get("id", "")
        name = file.get("name", "")
        drive_path = file.get("drive_path") or name
        text = f"{drive_path} {name}"
        local_path = local_files.get(file_id)

        inventory.append(
            {
                "id": file_id,
                "name": name,
                "drive_path": drive_path,
                "local_path": str(local_path) if local_path else None,
                "floor_hint": infer_floor(text, allowed_floor_levels),
                "discipline_hint": infer_discipline(text),
                "modified_time": file.get("modified_time"),
                "checksum": file.get("checksum"),
                "status": "downloaded" if local_path else "metadata_only",
            }
        )

    json_path = output_dir / "dwg-inventory.json"
    csv_path = output_dir / "dwg-inventory.csv"
    json_path.write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_inventory_csv(csv_path, inventory)
    return inventory


def infer_floor(text: str, allowed_floor_levels: list[int] | None = None) -> str | None:
    for pattern, formatter in FLOOR_PATTERNS:
        match = pattern.search(text)
        if match:
            floor = formatter(match)
            if _is_allowed_floor(floor, allowed_floor_levels):
                return floor
    return None


def infer_discipline(text: str) -> str | None:
    normalized = text.casefold()
    for discipline, keywords in DISCIPLINE_KEYWORDS.items():
        if any(keyword.casefold() in normalized for keyword in keywords):
            return discipline
    return None


def summarize_inventory(inventory: list[dict]) -> dict[str, dict[str, int]]:
    return {
        "status": _count_by(inventory, "status"),
        "floor_hint": _count_by(inventory, "floor_hint"),
        "discipline_hint": _count_by(inventory, "discipline_hint"),
    }


def _load_drive_files(metadata_path: Path) -> list[dict]:
    if not metadata_path.exists():
        return []
    return json.loads(metadata_path.read_text(encoding="utf-8"))


def _index_local_dwg_files(raw_dir: Path, file_ids: list[str]) -> dict[str, Path]:
    files: dict[str, Path] = {}
    if not raw_dir.exists():
        return files

    drive_files = _load_drive_files(raw_dir.parent / "metadata" / "drive-files.json")
    drive_path_by_id = {
        str(file.get("id") or ""): str(file.get("drive_path") or file.get("name") or "")
        for file in drive_files
    }
    for file_id, drive_path in drive_path_by_id.items():
        if not file_id or not drive_path:
            continue
        path_parts = Path(drive_path).parts
        safe_parts = [_safe_filename(part) for part in path_parts]
        local_path = raw_dir.joinpath(*safe_parts)
        if local_path.exists():
            files[file_id] = local_path

    # Backward compatibility for older downloads that still have id-prefixed
    # filenames. The cleanup command removes these prefixes in-place.
    sorted_file_ids = sorted((file_id for file_id in file_ids if file_id), key=len, reverse=True)
    for path in raw_dir.rglob("*"):
        if not path.is_file() or path.suffix.casefold() != ".dwg":
            continue
        for file_id in sorted_file_ids:
            if path.name.startswith(f"{file_id}_") and file_id not in files:
                files[file_id] = path
                break
    return files


def _write_inventory_csv(path: Path, inventory: list[dict]) -> None:
    fieldnames = [
        "id",
        "name",
        "drive_path",
        "local_path",
        "floor_hint",
        "discipline_hint",
        "modified_time",
        "checksum",
        "status",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(inventory)


def _count_by(inventory: list[dict], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in inventory:
        key = item.get(field) or "unknown"
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _is_allowed_floor(floor: str, allowed_floor_levels: list[int] | None) -> bool:
    if not allowed_floor_levels:
        return True
    match = re.fullmatch(r"(\d+)F", floor)
    return bool(match and int(match.group(1)) in allowed_floor_levels)


def _safe_filename(name: str) -> str:
    blocked = '<>:"/\\|?*'
    safe = "".join("_" if char in blocked else char for char in name).strip()
    return safe or "unnamed-drawing"
