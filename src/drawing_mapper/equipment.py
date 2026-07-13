from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path

from drawing_mapper.models import DrawingPage


@dataclass(frozen=True)
class EquipmentCandidate:
    label: str
    drawing_x: float
    drawing_y: float
    confidence: float
    keyword: str | None = None
    category: str | None = None


def find_equipment_candidates(page: DrawingPage, keywords: list[str]) -> list[EquipmentCandidate]:
    normalized_keywords = {keyword.upper() for keyword in keywords}
    candidates: list[EquipmentCandidate] = []

    for text in page.texts:
        label = text.text.strip()
        if any(keyword in label.upper() for keyword in normalized_keywords):
            matched_keyword = next(
                keyword for keyword in normalized_keywords if keyword in label.upper()
            )
            candidates.append(
                EquipmentCandidate(
                    label=label,
                    drawing_x=text.x + text.width / 2,
                    drawing_y=text.y + text.height / 2,
                    confidence=0.6,
                    keyword=matched_keyword,
                )
            )

    return candidates


def extract_equipment_candidates_from_parsed_dir(
    parsed_dir: Path,
    keywords: dict[str, list[str]],
    output_dir: Path,
    allowed_floor_levels: list[int] | None = None,
    include_architecture: bool = False,
) -> list[dict]:
    output_dir.mkdir(parents=True, exist_ok=True)
    candidates: list[dict] = []

    # First pass: scan every parsed drawing text item and keep anything that
    # matches the equipment keyword dictionary.
    for path in sorted(parsed_dir.rglob("*.json")):
        if path.name == "parse-manifest.json":
            continue
        parsed = json.loads(path.read_text(encoding="utf-8-sig"))
        if parsed.get("status") != "parsed":
            continue

        source_text = f"{parsed.get('source_path') or ''} {parsed.get('drawing_file_id') or ''}"
        floor_hint = _infer_floor(source_text, allowed_floor_levels)
        discipline_hint = _infer_discipline(source_text)
        if discipline_hint == "architecture" and not include_architecture:
            continue

        for page in parsed.get("pages", []):
            page_floor_markers = _extract_page_floor_markers(page, allowed_floor_levels)
            for text in page.get("texts", []):
                label = str(text.get("text") or "").strip()
                if not label:
                    continue
                label_floor_hint = _infer_floor(label, allowed_floor_levels)
                nearest_floor_hint = _nearest_floor_hint(
                    text,
                    page_floor_markers,
                    max_distance=25000,
                )
                for category, category_keywords in keywords.items():
                    keyword = _match_keyword(label, category_keywords)
                    if not keyword:
                        continue
                    candidates.append(
                        {
                            "category": category,
                            "keyword": keyword,
                            "label": label,
                            "drawing_x": float(text.get("x") or 0),
                            "drawing_y": float(text.get("y") or 0),
                            "page_number": page.get("page_number"),
                            "floor_hint": label_floor_hint or nearest_floor_hint or floor_hint,
                            "discipline_hint": discipline_hint,
                            "drawing_file_id": parsed.get("drawing_file_id"),
                            "source_path": parsed.get("source_path"),
                            "parsed_json_path": str(path),
                            "confidence": 0.6,
                        }
                    )
                    break

    json_path = output_dir / "equipment-candidates.json"
    csv_path = output_dir / "equipment-candidates.csv"
    summary_json_path = output_dir / "equipment-candidates-summary.json"
    summary_csv_path = output_dir / "equipment-candidates-summary.csv"
    json_path.write_text(json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_candidates_csv(csv_path, candidates)

    # Second pass: collapse repeated labels per drawing so review files are smaller.
    summarized = summarize_candidates(candidates)
    summary_json_path.write_text(
        json.dumps(summarized, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_summary_csv(summary_csv_path, summarized)

    # Third pass: remove obvious notes, legends, schedules, and discipline mismatches.
    refined = refine_candidates(summarized)
    refined_json_path = output_dir / "equipment-candidates-refined.json"
    refined_csv_path = output_dir / "equipment-candidates-refined.csv"
    refined_json_path.write_text(
        json.dumps(refined, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_summary_csv(refined_csv_path, refined)
    _write_floor_files(output_dir, refined, folder_name="equipment-by-floor")

    # Final pass: keep only drawings that are likely to contain actual location
    # coordinates, such as floor plans and equipment layout drawings.
    location_candidates = filter_location_candidates(refined)
    location_json_path = output_dir / "equipment-location-candidates.json"
    location_csv_path = output_dir / "equipment-location-candidates.csv"
    location_json_path.write_text(
        json.dumps(location_candidates, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_summary_csv(location_csv_path, location_candidates)
    _write_floor_files(output_dir, location_candidates, folder_name="equipment-location-by-floor")
    facility_locations = dedupe_location_candidates(location_candidates)
    facility_json_path = output_dir / "facility-location-draft.json"
    facility_csv_path = output_dir / "facility-location-draft.csv"
    facility_json_path.write_text(
        json.dumps(facility_locations, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_facility_locations_csv(facility_csv_path, facility_locations)
    high_confidence_locations = filter_high_confidence_locations(facility_locations)
    high_confidence_json_path = output_dir / "facility-location-high-confidence.json"
    high_confidence_csv_path = output_dir / "facility-location-high-confidence.csv"
    high_confidence_json_path.write_text(
        json.dumps(high_confidence_locations, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_facility_locations_csv(high_confidence_csv_path, high_confidence_locations)
    return candidates


def load_equipment_keywords(path: Path) -> dict[str, list[str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(key): [str(value) for value in values] for key, values in data.items()}


def _match_keyword(label: str, keywords: list[str]) -> str | None:
    normalized = label.casefold()
    for keyword in keywords:
        if _keyword_matches(normalized, keyword):
            return keyword
    return None


def _keyword_matches(normalized_label: str, keyword: str) -> bool:
    normalized_keyword = keyword.casefold()
    if re.fullmatch(r"[a-z0-9]+", normalized_keyword):
        pattern = rf"(?<![a-z0-9]){re.escape(normalized_keyword)}(?![a-z0-9])"
        return bool(re.search(pattern, normalized_label))
    return normalized_keyword in normalized_label


def _infer_floor(text: str, allowed_floor_levels: list[int] | None = None) -> str | None:
    # Only known building floors are accepted. This avoids treating drawing numbers
    # or dates as fake floors like 103F while still keeping project-specific
    # service levels such as PIT, PH, and PHR out of the unknown bucket.
    patterns = [
        (re.compile(r"\uc625\ud0d1\s*\uc9c0\ubd95\s*\uce35|P\s*H\s*R", re.IGNORECASE), lambda match: "PHR"),
        (re.compile(r"\uc625\ud0d1\s*\uce35|\uc625\ud0d1|P\s*H\s*(?:\uce35|FLOOR|FL\b)", re.IGNORECASE), lambda match: "PH"),
        (re.compile(r"(?<![A-Z0-9])PIT(?![A-Z0-9])|\ud53c\ud2b8", re.IGNORECASE), lambda match: "PIT"),
        (re.compile(r"\uc9c0\uc0c1\s*([1-6])\s*\uce35"), lambda match: f"{match.group(1)}F"),
        (re.compile(r"([1-6])\s*\uce35"), lambda match: f"{match.group(1)}F"),
        (re.compile(r"([1-6])\s*F", re.IGNORECASE), lambda match: f"{match.group(1)}F"),
        (re.compile(r"ROOF|\uc625\uc0c1", re.IGNORECASE), lambda match: "ROOF"),
    ]
    for pattern, formatter in patterns:
        match = pattern.search(text)
        if match:
            floor = formatter(match)
            if _is_allowed_floor(floor, allowed_floor_levels):
                return floor
    return None


def _extract_page_floor_markers(
    page: dict,
    allowed_floor_levels: list[int] | None,
) -> list[dict]:
    markers = []
    for text in page.get("texts", []):
        value = str(text.get("text") or "")
        floor = _infer_floor(value, allowed_floor_levels)
        if not floor:
            continue
        markers.append(
            {
                "floor": floor,
                "x": float(text.get("x") or 0),
                "y": float(text.get("y") or 0),
            }
        )
    return markers


def _nearest_floor_hint(
    text: dict,
    floor_markers: list[dict],
    max_distance: float,
) -> str | None:
    if not floor_markers:
        return None
    x = float(text.get("x") or 0)
    y = float(text.get("y") or 0)
    nearest = min(
        floor_markers,
        key=lambda marker: ((float(marker["x"]) - x) ** 2 + (float(marker["y"]) - y) ** 2),
    )
    distance = ((float(nearest["x"]) - x) ** 2 + (float(nearest["y"]) - y) ** 2) ** 0.5
    if distance <= max_distance:
        return str(nearest["floor"])
    return None


def _infer_discipline(text: str) -> str | None:
    normalized = text.casefold()
    slash_text = normalized.replace("\\", "/")
    # Folder prefixes are more reliable than text labels for this project.
    prefix_hints = {
        "architecture": r"04_[^/]+/01_",
        "electrical": r"04_[^/]+/02_",
        "mechanical": r"04_[^/]+/03_",
        "telecom": r"04_[^/]+/04_",
    }
    for discipline, pattern in prefix_hints.items():
        if re.search(pattern, slash_text):
            return discipline

    hints = {
        "mechanical": ["\uae30\uacc4", "\uacf5\uc870", "\ubc30\uad00"],
        "electrical": ["\uc804\uae30", "\ub3d9\ub825", "\uc804\ub825"],
        "telecom": ["\ud1b5\uc2e0", "cctv", "bms", "dcim"],
        "architecture": ["\uac74\ucd95", "\uad6c\uc870"],
    }
    for discipline, keywords in hints.items():
        if any(keyword.casefold() in normalized for keyword in keywords):
            return discipline
    return None


def _write_candidates_csv(path: Path, candidates: list[dict]) -> None:
    fieldnames = [
        "category",
        "keyword",
        "label",
        "drawing_x",
        "drawing_y",
        "page_number",
        "floor_hint",
        "discipline_hint",
        "drawing_file_id",
        "source_path",
        "parsed_json_path",
        "confidence",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(candidates)


def summarize_candidates(candidates: list[dict]) -> list[dict]:
    grouped: dict[tuple, dict] = {}
    for candidate in candidates:
        # Same label in the same drawing is grouped, while separate drawings remain
        # separate so duplicated source files can still be reviewed.
        key = (
            candidate.get("category"),
            candidate.get("keyword"),
            candidate.get("label"),
            candidate.get("floor_hint") or "unknown",
            candidate.get("discipline_hint") or "unknown",
            candidate.get("drawing_file_id"),
        )
        item = grouped.setdefault(
            key,
            {
                "category": candidate.get("category"),
                "keyword": candidate.get("keyword"),
                "label": candidate.get("label"),
                "floor_hint": candidate.get("floor_hint"),
                "discipline_hint": candidate.get("discipline_hint"),
                "drawing_file_id": candidate.get("drawing_file_id"),
                "source_path": candidate.get("source_path"),
                "count": 0,
                "sample_x": candidate.get("drawing_x"),
                "sample_y": candidate.get("drawing_y"),
                "confidence": candidate.get("confidence"),
            },
        )
        item["count"] += 1

    return sorted(
        grouped.values(),
        key=lambda item: (
            str(item.get("discipline_hint") or ""),
            str(item.get("floor_hint") or ""),
            str(item.get("category") or ""),
            str(item.get("label") or ""),
        ),
    )


def refine_candidates(candidates: list[dict]) -> list[dict]:
    refined = []
    allowed_by_discipline = {
        "electrical": {"electrical", "power", "it_power", "monitoring_control", "telecom", "fire"},
        "mechanical": {"mechanical", "cooling", "plumbing", "power", "it_power", "fire", "monitoring_control"},
        "telecom": {"telecom", "monitoring_control", "power", "it_power", "electrical", "fire"},
    }

    for candidate in candidates:
        label = str(candidate.get("label") or "").strip()
        category = str(candidate.get("category") or "")
        discipline = str(candidate.get("discipline_hint") or "")

        if not _looks_like_equipment_label(label):
            continue
        if discipline == "architecture":
            continue
        if discipline in allowed_by_discipline and category not in allowed_by_discipline[discipline]:
            continue

        item = dict(candidate)
        item["confidence"] = _refined_confidence(item)
        refined.append(item)

    return sorted(
        refined,
        key=lambda item: (
            -(float(item.get("confidence") or 0)),
            str(item.get("discipline_hint") or ""),
            str(item.get("floor_hint") or ""),
            str(item.get("label") or ""),
        ),
    )


def filter_location_candidates(candidates: list[dict]) -> list[dict]:
    location_candidates = []
    for candidate in candidates:
        source_path = str(candidate.get("source_path") or "")
        drawing_file_id = str(candidate.get("drawing_file_id") or "")
        source_text = f"{source_path} {drawing_file_id}"

        if not _is_location_drawing(source_text):
            continue
        if not _has_coordinate_like_sample(candidate):
            continue
        if not _looks_like_location_label(candidate):
            continue

        item = dict(candidate)
        item["confidence"] = min(round(float(item.get("confidence") or 0) + 0.05, 2), 0.98)
        location_candidates.append(item)

    return sorted(
        location_candidates,
        key=lambda item: (
            str(item.get("floor_hint") or "unknown"),
            str(item.get("discipline_hint") or ""),
            str(item.get("category") or ""),
            str(item.get("label") or ""),
        ),
    )


def dedupe_location_candidates(candidates: list[dict]) -> list[dict]:
    deduped: dict[tuple, dict] = {}
    for candidate in candidates:
        x = float(candidate.get("sample_x") or 0)
        y = float(candidate.get("sample_y") or 0)
        key = (
            candidate.get("floor_hint") or "unknown",
            candidate.get("discipline_hint") or "unknown",
            candidate.get("category") or "unknown",
            _normalize_label(str(candidate.get("label") or "")),
            round(x, 1),
            round(y, 1),
        )
        item = deduped.setdefault(
            key,
            {
                "floor": candidate.get("floor_hint") or "unknown",
                "discipline": candidate.get("discipline_hint"),
                "equipment_category": candidate.get("category"),
                "keyword": candidate.get("keyword"),
                "label": _clean_label(str(candidate.get("label") or "")),
                "drawing_x": x,
                "drawing_y": y,
                "confidence": candidate.get("confidence"),
                "source_count": 0,
                "source_paths": [],
            },
        )
        item["source_count"] += int(candidate.get("count") or 1)
        source_path = candidate.get("source_path")
        if source_path and source_path not in item["source_paths"]:
            item["source_paths"].append(source_path)
        item["confidence"] = max(float(item.get("confidence") or 0), float(candidate.get("confidence") or 0))

    for item in deduped.values():
        item["source_paths"] = item["source_paths"][:5]

    return sorted(
        deduped.values(),
        key=lambda item: (
            str(item.get("floor") or "unknown"),
            str(item.get("discipline") or ""),
            str(item.get("equipment_category") or ""),
            str(item.get("label") or ""),
        ),
    )


def filter_high_confidence_locations(locations: list[dict]) -> list[dict]:
    filtered = []
    for location in locations:
        if location.get("floor") == "unknown":
            continue
        if not _looks_like_high_confidence_facility_label(location):
            continue

        item = dict(location)
        item["confidence"] = min(round(float(item.get("confidence") or 0) + 0.03, 2), 0.99)
        filtered.append(item)

    return sorted(
        filtered,
        key=lambda item: (
            str(item.get("floor") or "unknown"),
            str(item.get("discipline") or ""),
            str(item.get("equipment_category") or ""),
            str(item.get("label") or ""),
        ),
    )


def _is_location_drawing(text: str) -> bool:
    normalized = text.casefold()
    # Keep plan/layout drawings and reject schedules, legends, system diagrams,
    # one-line diagrams, and other non-location drawings.
    include_terms = [
        "\ud3c9\uba74\ub3c4",
        "\ubc30\uce58\ub3c4",
        "\ud655\ub300\ud3c9\uba74",
        "\uc124\uce58\ub3c4",
    ]
    exclude_terms = [
        "\uacc4\ud1b5\ub3c4",
        "\uad6c\uc131\ub3c4",
        "\ubaa9\ub85d",
        "\uc77c\ub78c\ud45c",
        "\ubc94\ub840",
        "\uc8fc\uae30",
        "\uacb0\uc120\ub3c4",
        "\uc0c1\uc138\ub3c4",
        "\uc678\ud615\ub3c4",
        "\uad6c\ubd84\ud45c",
    ]
    return (
        any(term in normalized for term in include_terms)
        and not any(term in normalized for term in exclude_terms)
    )


def _has_coordinate_like_sample(candidate: dict) -> bool:
    try:
        x = float(candidate.get("sample_x"))
        y = float(candidate.get("sample_y"))
    except (TypeError, ValueError):
        return False
    return x != 0 or y != 0


def _looks_like_location_label(candidate: dict) -> bool:
    label = str(candidate.get("label") or "").strip()
    keyword = str(candidate.get("keyword") or "").strip()

    # Relay numbers are useful classification keywords, but a standalone "50"
    # or "51" text is not a physical equipment location by itself.
    if keyword.isdigit() and label == keyword:
        return False

    lowered = label.casefold()
    if label.startswith(("TO.", "FROM.")):
        return False
    if any(token in lowered for token in ["program", "software", "sw \uc218\ub7c9"]):
        return False
    if any(token in label for token in ["\uc218\ub7c9", "\ud504\ub85c\uadf8\ub7a8"]):
        return False

    if _looks_like_drawing_note(label):
        return False

    return True


def _looks_like_high_confidence_facility_label(location: dict) -> bool:
    label = str(location.get("label") or "").strip()
    keyword = str(location.get("keyword") or "").strip()
    category = str(location.get("equipment_category") or "")

    if not label or _looks_like_drawing_note(label):
        return False
    if keyword.isdigit() and not re.search(r"\uacc4\uc804|relay", label, re.IGNORECASE):
        return False

    normalized_label = _clean_label(label).casefold()
    normalized_keyword = keyword.casefold()
    if normalized_label == normalized_keyword:
        return normalized_keyword not in _short_ambiguous_location_keywords()

    strong_terms = [
        "rack",
        "bank",
        "duct",
        "tray",
        "panel",
        "switchgear",
        "\uc2e4",
        "\ubc18",
        "\uae30",
        "\ud0f1\ud06c",
        "\ubc38\ube0c",
        "\ud32c",
        "\ud38c\ud504",
        "\ub355\ud2b8",
        "\ub0c9\ub3d9\uae30",
        "\ubc1c\uc804\uae30",
        "\ubcc0\uc555\uae30",
        "\ubd84\uc804\ubc18",
        "\uc218\ubc30\uc804",
        "\uacf5\uc870\uc2e4",
    ]
    if any(term in normalized_label for term in strong_terms):
        return True
    if re.search(r"[A-Za-z]{2,}[-_.#]?\d", label):
        return True
    if category in {"cooling", "power", "it_power"} and re.search(r"[A-Za-z]{2,}[-_.][A-Za-z0-9]", label):
        return True

    return False


def _short_ambiguous_location_keywords() -> set[str]:
    return {
        "27",
        "50",
        "51",
        "59",
        "87",
        "acb",
        "ahu",
        "ats",
        "bms",
        "cwu",
        "dcim",
        "epms",
        "fms",
        "gis",
        "hv",
        "io",
        "i/o",
        "lan",
        "lv",
        "mcc",
        "mhv",
        "ngr",
        "pdu",
        "rpp",
        "sts",
        "thd",
        "tr",
        "ups",
        "vcb",
    }


def _looks_like_drawing_note(label: str) -> bool:
    lowered = label.casefold()
    note_terms = [
        "scale",
        "\ucd95\ucc99",
        "\uc124\uce58\ud560 \uac83",
        "\uc124\uce58 \ud560 \uac83",
        "\ud560 \uac83",
        "\uc0ac\uc6a9\ud55c\ub2e4",
        "\uc0ad\uc81c",
        "\ubcc0\uacbd",
        "\uac00\uc7a5 \uac00\uae4c\uc6b4",
        "\uac00\ub2a5\ud558\ub3c4\ub85d",
        "\ucd5c\uc18c",
        "\uc774\uc0c1",
        "\uc73c\ub85c\ubd80\ud130",
        "assembly",
        "indicator",
        "indigator",
    ]
    if any(term in lowered for term in note_terms):
        return True
    if re.search(r"^\d+\s*[:/]\s*\d+", label):
        return True
    if re.search(r"^\d+\s*\u00f8", label, re.IGNORECASE):
        return True
    return False


def _looks_like_equipment_label(label: str) -> bool:
    if len(label) > 60:
        return False
    if label.startswith(("*", "-", "\u203b")):
        return False
    if re.match(r"^\d+\.", label):
        return False
    if label.startswith(("\uc608)", "ex)", "EX)")):
        return False
    if any(token in label.casefold() for token in ["scope", "excluded", "\uc81c\uc678", "\ud3ec\ud568"]):
        return False
    if any(
        token in label
        for token in [
            "\ud3c9\uba74\ub3c4",
            "\uacc4\ud1b5\ub3c4",
            "\uad6c\uc131\ub3c4",
            "\ubaa9\ub85d\ud45c",
            "\uc77c\ub78c\ud45c",
            "\ubc94\ub840",
            "\uc8fc\uae30\uc0ac\ud56d",
        ]
    ):
        return False
    return bool(re.search(r"[A-Za-z0-9\uac00-\ud7a3]", label))


def _normalize_label(label: str) -> str:
    return re.sub(r"\s+", " ", _clean_label(label)).casefold()


def _clean_label(label: str) -> str:
    return label.replace("%%U", "").strip()


def _refined_confidence(candidate: dict) -> float:
    label = str(candidate.get("label") or "")
    confidence = 0.6
    if candidate.get("floor_hint"):
        confidence += 0.1
    if re.search(r"\b[A-Z]+[-_.]?\d+", label):
        confidence += 0.15
    if re.search(r"[1-6]F|[1-6]\uce35", label, re.IGNORECASE):
        confidence += 0.1
    if int(candidate.get("count") or 0) > 1:
        confidence += 0.05
    return min(round(confidence, 2), 0.95)


def _write_summary_csv(path: Path, rows: list[dict]) -> None:
    fieldnames = [
        "category",
        "keyword",
        "label",
        "floor_hint",
        "discipline_hint",
        "drawing_file_id",
        "source_path",
        "count",
        "sample_x",
        "sample_y",
        "confidence",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_facility_locations_csv(path: Path, rows: list[dict]) -> None:
    fieldnames = [
        "floor",
        "discipline",
        "equipment_category",
        "keyword",
        "label",
        "drawing_x",
        "drawing_y",
        "confidence",
        "source_count",
        "source_paths",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            output = dict(row)
            output["source_paths"] = " | ".join(row.get("source_paths") or [])
            writer.writerow(output)


def _write_floor_files(output_dir: Path, rows: list[dict], folder_name: str) -> None:
    by_floor: dict[str, list[dict]] = {}
    for row in rows:
        floor = row.get("floor_hint") or "unknown"
        by_floor.setdefault(str(floor), []).append(row)

    floor_dir = output_dir / folder_name
    floor_dir.mkdir(parents=True, exist_ok=True)
    for floor, floor_rows in sorted(by_floor.items()):
        safe_floor = re.sub(r"[^A-Za-z0-9_-]+", "_", floor)
        _write_summary_csv(floor_dir / f"{safe_floor}.csv", floor_rows)

    index = []
    for floor, floor_rows in sorted(by_floor.items()):
        safe_floor = re.sub(r"[^A-Za-z0-9_-]+", "_", floor)
        index.append(
            {
                "floor": floor,
                "count": len(floor_rows),
                "csv_path": str(floor_dir / f"{safe_floor}.csv"),
            }
        )
    (floor_dir / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _is_allowed_floor(floor: str, allowed_floor_levels: list[int] | None) -> bool:
    if floor in {"PIT", "PH", "PHR", "ROOF"}:
        return True
    if not allowed_floor_levels:
        return True
    match = re.fullmatch(r"([1-9]\d*)F", floor)
    return bool(match and int(match.group(1)) in allowed_floor_levels)
