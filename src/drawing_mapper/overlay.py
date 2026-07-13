from __future__ import annotations

import csv
import json
import re
import shutil
from pathlib import Path


PLAN_TOKENS = ["plan", "site", "\ubc30\uce58", "\uc7a5\ube44", "\ud3c9\uba74"]


def build_overlay_plan(
    xref_inventory_path: Path,
    facility_locations_path: Path | None,
    output_dir: Path,
) -> dict:
    xref_rows = _read_csv(xref_inventory_path)
    facility_counts = _facility_counts_by_source(facility_locations_path)

    drawing_rows = []
    for row in xref_rows:
        if str(row.get("status") or "") != "parsed":
            continue
        if not _is_plan_like(row):
            continue
        if not _has_transform(row):
            continue
        drawing_rows.append(_overlay_drawing_row(row, facility_counts))

    groups = _group_overlay_rows(drawing_rows)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "drawing-overlay-drawings.csv", drawing_rows)
    _write_csv(output_dir / "drawing-overlay-groups.csv", groups)
    (output_dir / "drawing-overlay-drawings.json").write_text(
        json.dumps(drawing_rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "drawing-overlay-groups.json").write_text(
        json.dumps(groups, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    report = {
        "xref_inventory": str(xref_inventory_path),
        "facility_locations": str(facility_locations_path) if facility_locations_path else "",
        "overlay_drawing_count": len(drawing_rows),
        "overlay_group_count": len(groups),
        "identity_group_count": sum(1 for group in groups if group["is_identity_insert"] == "True"),
        "top_groups": groups[:20],
        "outputs": {
            "drawings_csv": str(output_dir / "drawing-overlay-drawings.csv"),
            "groups_csv": str(output_dir / "drawing-overlay-groups.csv"),
            "drawings_json": str(output_dir / "drawing-overlay-drawings.json"),
            "groups_json": str(output_dir / "drawing-overlay-groups.json"),
        },
    }
    (output_dir / "drawing-overlay-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report


def collect_xr_plan_raw_drawings(
    overlay_drawings_path: Path,
    raw_root: Path,
    output_dir: Path,
    priority: str | None = None,
    dry_run: bool = False,
) -> dict:
    rows = _read_csv(overlay_drawings_path)
    selected = []
    for row in rows:
        if not _is_xr_plan_row(row):
            continue
        if priority and str(row.get("overlay_priority") or "") != priority:
            continue
        selected.append(row)

    output_raw_dir = output_dir / "xr-plan-raw"
    manifest_rows = []
    copied = 0
    missing = 0
    planned = 0

    for row in sorted(
        selected,
        key=lambda item: (
            _priority_rank(str(item.get("overlay_priority") or "")),
            -int(str(item.get("facility_count") or "0") or 0),
            str(item.get("drawing_path") or ""),
        ),
    ):
        converted_path = Path(str(row.get("drawing_path") or ""))
        raw_path = _converted_dxf_to_raw_dwg(converted_path, raw_root)
        copied_path = output_raw_dir / raw_path.relative_to(raw_root) if raw_path else None
        status = "missing_raw"

        if raw_path and raw_path.exists() and copied_path:
            status = "planned" if dry_run else "copied"
            planned += 1
            if not dry_run:
                copied_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(raw_path, copied_path)
                copied += 1
        else:
            missing += 1

        manifest_rows.append(
            {
                "status": status,
                "overlay_priority": str(row.get("overlay_priority") or ""),
                "overlay_group_id": str(row.get("overlay_group_id") or ""),
                "drawing_name": str(row.get("drawing_name") or ""),
                "facility_count": str(row.get("facility_count") or ""),
                "raw_path": str(raw_path) if raw_path else "",
                "copied_path": str(copied_path) if copied_path else "",
                "converted_path": str(converted_path),
                "basis_name": str(row.get("basis_name") or ""),
                "basis_path": str(row.get("basis_path") or ""),
                "insert_x": str(row.get("insert_x") or ""),
                "insert_y": str(row.get("insert_y") or ""),
                "xscale": str(row.get("xscale") or ""),
                "yscale": str(row.get("yscale") or ""),
                "rotation": str(row.get("rotation") or ""),
                "is_identity_insert": str(row.get("is_identity_insert") or ""),
                "review_status": "",
                "review_note": "",
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "xr-plan-raw-manifest.csv", manifest_rows)
    (output_dir / "xr-plan-raw-manifest.json").write_text(
        json.dumps(manifest_rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    report = {
        "overlay_drawings": str(overlay_drawings_path),
        "raw_root": str(raw_root),
        "output_raw_dir": str(output_raw_dir),
        "selected_count": len(selected),
        "copied_count": copied,
        "planned_count": planned,
        "missing_count": missing,
        "dry_run": dry_run,
        "priority_filter": priority or "",
        "manifest_csv": str(output_dir / "xr-plan-raw-manifest.csv"),
        "manifest_json": str(output_dir / "xr-plan-raw-manifest.json"),
    }
    (output_dir / "xr-plan-raw-collection-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report


def _overlay_drawing_row(row: dict, facility_counts: dict[str, int]) -> dict:
    drawing_path = str(row.get("drawing_path") or "")
    xref_name = str(row.get("xref_name") or "")
    insert_x = _format_number(row.get("insert_x"))
    insert_y = _format_number(row.get("insert_y"))
    xscale = _format_number(row.get("xscale"), default="1")
    yscale = _format_number(row.get("yscale"), default="1")
    rotation = _format_number(row.get("rotation"), default="0")
    transform_key = "|".join([xref_name.casefold(), insert_x, insert_y, xscale, yscale, rotation])
    identity = str(row.get("is_identity_insert") or "")

    return {
        "overlay_group_id": _safe_group_id(transform_key),
        "overlay_priority": _overlay_priority(row, facility_counts.get(_path_key(drawing_path), 0)),
        "basis_name": xref_name,
        "basis_file": str(row.get("xref_file") or ""),
        "basis_path": str(row.get("xref_path") or ""),
        "floor_hint": str(row.get("floor_hint") or ""),
        "drawing_name": str(row.get("drawing_name") or ""),
        "drawing_path": drawing_path,
        "relative_drawing_path": str(row.get("relative_drawing_path") or ""),
        "facility_count": str(facility_counts.get(_path_key(drawing_path), 0)),
        "insert_x": insert_x,
        "insert_y": insert_y,
        "xscale": xscale,
        "yscale": yscale,
        "rotation": rotation,
        "is_identity_insert": identity,
        "review_note": _review_note(row),
    }


def _group_overlay_rows(rows: list[dict]) -> list[dict]:
    groups: dict[str, dict] = {}
    for row in rows:
        group_id = row["overlay_group_id"]
        group = groups.setdefault(
            group_id,
            {
                "overlay_group_id": group_id,
                "overlay_priority": row["overlay_priority"],
                "basis_name": row["basis_name"],
                "basis_file": row["basis_file"],
                "basis_path": row["basis_path"],
                "floor_hint": row["floor_hint"],
                "insert_x": row["insert_x"],
                "insert_y": row["insert_y"],
                "xscale": row["xscale"],
                "yscale": row["yscale"],
                "rotation": row["rotation"],
                "is_identity_insert": row["is_identity_insert"],
                "drawing_count": 0,
                "facility_count": 0,
                "sample_drawings": [],
                "review_note": row["review_note"],
            },
        )
        group["drawing_count"] += 1
        group["facility_count"] += int(row["facility_count"] or 0)
        if len(group["sample_drawings"]) < 8:
            group["sample_drawings"].append(row["drawing_name"])
        if _priority_rank(row["overlay_priority"]) < _priority_rank(group["overlay_priority"]):
            group["overlay_priority"] = row["overlay_priority"]

    output = []
    for group in groups.values():
        group["drawing_count"] = str(group["drawing_count"])
        group["facility_count"] = str(group["facility_count"])
        group["sample_drawings"] = " | ".join(group["sample_drawings"])
        output.append(group)

    return sorted(
        output,
        key=lambda group: (
            _priority_rank(str(group["overlay_priority"])),
            -int(group["facility_count"] or 0),
            -int(group["drawing_count"] or 0),
            str(group["basis_name"]).casefold(),
        ),
    )


def _overlay_priority(row: dict, facility_count: int) -> str:
    text = f"{row.get('xref_name') or ''} {row.get('xref_path') or ''}".casefold()
    identity = str(row.get("is_identity_insert") or "").casefold() == "true"
    if "xr-plan" in text and identity:
        return "A_XR_PLAN_IDENTITY"
    if "xr-plan" in text:
        return "B_XR_PLAN_TRANSFORMED"
    if ("x-site" in text or "site" in text) and facility_count:
        return "C_SITE_WITH_FACILITIES"
    if "plan" in text and facility_count:
        return "D_FLOOR_PLAN_WITH_FACILITIES"
    if facility_count:
        return "E_OTHER_WITH_FACILITIES"
    return "Z_REFERENCE_ONLY"


def _priority_rank(priority: str) -> int:
    order = {
        "A_XR_PLAN_IDENTITY": 0,
        "B_XR_PLAN_TRANSFORMED": 1,
        "C_SITE_WITH_FACILITIES": 2,
        "D_FLOOR_PLAN_WITH_FACILITIES": 3,
        "E_OTHER_WITH_FACILITIES": 4,
        "Z_REFERENCE_ONLY": 9,
    }
    return order.get(priority, 99)


def _review_note(row: dict) -> str:
    identity = str(row.get("is_identity_insert") or "").casefold() == "true"
    if identity:
        return "Can be overlaid directly on basis coordinates."
    return "Apply inverse insert/scale/rotation before comparing with basis coordinates."


def _is_xr_plan_row(row: dict) -> bool:
    text = f"{row.get('basis_name') or ''} {row.get('basis_path') or ''}".casefold()
    return "xr-plan" in text


def _converted_dxf_to_raw_dwg(converted_path: Path, raw_root: Path) -> Path | None:
    parts = converted_path.parts
    lowered = [part.casefold() for part in parts]
    try:
        data_index = lowered.index("data")
        converted_index = lowered.index("converted")
        dxf_index = lowered.index("dxf")
    except ValueError:
        return None
    if converted_index != data_index + 1 or dxf_index != converted_index + 1:
        return None
    relative = Path(*parts[dxf_index + 1 :]).with_suffix(".dwg")
    return raw_root / relative


def _is_plan_like(row: dict) -> bool:
    name = str(row.get("xref_name") or "")
    if name.startswith(("*D", "*U")):
        return False
    text = f"{name} {row.get('xref_path') or ''} {row.get('xref_file') or ''}".casefold()
    return any(token in text for token in PLAN_TOKENS)


def _has_transform(row: dict) -> bool:
    return _to_float(row.get("insert_x")) is not None and _to_float(row.get("insert_y")) is not None


def _facility_counts_by_source(path: Path | None) -> dict[str, int]:
    if not path or not path.exists():
        return {}
    counts: dict[str, int] = {}
    for row in _read_csv(path):
        paths = str(row.get("source_paths") or row.get("primary_source_path") or "")
        if not paths:
            continue
        for source_path in [part.strip() for part in paths.split("|") if part.strip()]:
            key = _path_key(source_path)
            counts[key] = counts.get(key, 0) + 1
    return counts


def _path_key(value: str) -> str:
    return value.replace("/", "\\").strip().casefold()


def _safe_group_id(value: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z._-]+", "_", value).strip("_")
    return cleaned[:96] or "overlay_group"


def _format_number(value: object, default: str = "") -> str:
    parsed = _to_float(value)
    if parsed is None:
        return default
    if abs(parsed) < 1e-8:
        parsed = 0.0
    return f"{parsed:.12g}"


def _to_float(value: object) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _read_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def _write_csv(path: Path, rows: list[dict]) -> None:
    if rows:
        fieldnames = list(rows[0].keys())
    else:
        fieldnames = [
            "overlay_group_id",
            "overlay_priority",
            "basis_name",
            "basis_file",
            "basis_path",
            "floor_hint",
        ]
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
