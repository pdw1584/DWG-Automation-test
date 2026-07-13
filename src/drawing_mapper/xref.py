from __future__ import annotations

import csv
import json
import math
import re
from pathlib import Path


XREF_BLOCK_FLAG = 4
XREF_OVERLAY_FLAG = 8

# 외부참조 리스트 만들기
def build_xref_inventory(input_dir: Path, output_dir: Path) -> list[dict]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []

    for path in sorted(input_dir.rglob("*.dxf")):
        rows.extend(_extract_xrefs(path, input_dir))

    json_path = output_dir / "xref-inventory.json"
    csv_path = output_dir / "xref-inventory.csv"
    summary_json_path = output_dir / "xref-summary.json"
    summary_csv_path = output_dir / "xref-summary.csv"
    plan_json_path = output_dir / "xref-plan-candidates.json"
    plan_csv_path = output_dir / "xref-plan-candidates.csv"

    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_csv(csv_path, rows)

    summary = summarize_xrefs(rows)
    summary_json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_csv(summary_csv_path, summary)
    plan_candidates = filter_plan_xrefs(rows)
    plan_json_path.write_text(
        json.dumps(plan_candidates, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_csv(plan_csv_path, plan_candidates)
    return rows


# 좌표 기준으로 쓸 가능성이 높은 PLAN/SITE 계열 외부참조만 추리기
def filter_plan_xrefs(rows: list[dict]) -> list[dict]:
    candidates = []
    for row in rows:
        text = f"{row.get('xref_name') or ''} {row.get('xref_path') or ''}".casefold()
        if not any(token in text for token in ["plan", "site", "배치", "평면"]):
            continue
        if str(row.get("xref_name") or "").startswith(("*D", "*U")):
            continue
        candidates.append(row)

    return sorted(
        candidates,
        key=lambda item: (
            str(item.get("is_identity_insert") or ""),
            str(item.get("xref_name") or "").casefold(),
            str(item.get("floor_hint") or ""),
            str(item.get("drawing_name") or "").casefold(),
        ),
        reverse=True,
    )


# 외부참조 요약
def summarize_xrefs(rows: list[dict]) -> list[dict]:
    grouped: dict[tuple, dict] = {}
    for row in rows:
        key = (
            row.get("xref_name") or "",
            row.get("xref_path") or "",
            row.get("floor_hint") or "",
            row.get("is_identity_insert") or "",
        )
        item = grouped.setdefault(
            key,
            {
                "xref_name": row.get("xref_name") or "",
                "xref_path": row.get("xref_path") or "",
                "floor_hint": row.get("floor_hint") or "",
                "is_identity_insert": row.get("is_identity_insert") or "",
                "drawing_count": 0,
                "insert_count": 0,
                "sample_drawing_path": row.get("drawing_path") or "",
            },
        )
        item["drawing_count"] += 1
        item["insert_count"] += int(row.get("insert_count") or 0)

    return sorted(
        grouped.values(),
        key=lambda item: (
            str(item.get("xref_name") or "").casefold(),
            str(item.get("floor_hint") or ""),
            str(item.get("xref_path") or "").casefold(),
        ),
    )

# 수집데이터들에서 외부참조 추출
def _extract_xrefs(path: Path, root: Path) -> list[dict]:
    try:
        blocks, inserts_by_name = _scan_dxf_xref_data(path)
    except Exception as exc:
        return [
            {
                "drawing_path": str(path),
                "relative_drawing_path": str(path.relative_to(root)),
                "drawing_name": path.name,
                "status": "failed",
                "message": str(exc),
            }
        ]

    rows = []
    for block in blocks:
        name = str(block.get("name") or "")
        flags = int(block.get("flags") or 0)
        xref_path = str(block.get("xref_path") or "")
        if not _is_xref_block(name, flags, xref_path):
            continue

        inserts = inserts_by_name.get(name, [])
        if inserts:
            for insert in inserts:
                rows.append(_xref_row(path, root, name, flags, xref_path, insert, "parsed"))
        else:
            rows.append(_xref_row(path, root, name, flags, xref_path, None, "parsed"))

    return rows


def _scan_dxf_xref_data(path: Path) -> tuple[list[dict], dict[str, list[dict]]]:
    blocks = []
    inserts_by_name: dict[str, list[dict]] = {}
    current_entity: dict | None = None
    current_type: str | None = None

    encoding = _detect_dxf_encoding(path)
    with path.open("r", encoding=encoding, errors="replace") as file:
        pair_iter = _iter_dxf_pairs(file)
        for code, value in pair_iter:
            if code == "0":
                if current_type == "BLOCK" and current_entity:
                    blocks.append(current_entity)
                elif current_type == "INSERT" and current_entity:
                    name = str(current_entity.get("name") or "")
                    if name:
                        current_entity.setdefault("insert_x", 0.0)
                        current_entity.setdefault("insert_y", 0.0)
                        current_entity.setdefault("insert_z", 0.0)
                        current_entity.setdefault("xscale", 1.0)
                        current_entity.setdefault("yscale", 1.0)
                        current_entity.setdefault("zscale", 1.0)
                        current_entity.setdefault("rotation", 0.0)
                        current_entity["is_identity_insert"] = _is_identity_insert(current_entity)
                        inserts_by_name.setdefault(name, []).append(current_entity)

                if value == "BLOCK":
                    current_type = "BLOCK"
                    current_entity = {}
                elif value == "INSERT":
                    current_type = "INSERT"
                    current_entity = {}
                else:
                    current_type = None
                    current_entity = None
                continue

            if current_entity is None:
                continue

            if current_type == "BLOCK":
                _read_block_pair(current_entity, code, value)
            elif current_type == "INSERT":
                _read_insert_pair(current_entity, code, value)

    if current_type == "BLOCK" and current_entity:
        blocks.append(current_entity)
    elif current_type == "INSERT" and current_entity:
        name = str(current_entity.get("name") or "")
        if name:
            current_entity.setdefault("insert_x", 0.0)
            current_entity.setdefault("insert_y", 0.0)
            current_entity.setdefault("insert_z", 0.0)
            current_entity.setdefault("xscale", 1.0)
            current_entity.setdefault("yscale", 1.0)
            current_entity.setdefault("zscale", 1.0)
            current_entity.setdefault("rotation", 0.0)
            current_entity["is_identity_insert"] = _is_identity_insert(current_entity)
            inserts_by_name.setdefault(name, []).append(current_entity)

    return blocks, inserts_by_name


def _detect_dxf_encoding(path: Path) -> str:
    sample = _read_binary_sample(path)
    if _looks_like_utf8(sample):
        return "utf-8"
    return "cp949"


def _read_binary_sample(path: Path, chunk_size: int = 1024 * 1024, max_chunks: int = 8) -> bytes:
    chunks = []
    with path.open("rb") as file:
        for _ in range(max_chunks):
            chunk = file.read(chunk_size)
            if not chunk:
                break
            chunks.append(chunk)
            if any(byte >= 128 for byte in chunk):
                break
    return b"".join(chunks)


def _looks_like_utf8(data: bytes) -> bool:
    if not data:
        return False
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    # ASCII-only files are safe under either encoding, but UTF-8 keeps mixed
    # ODA outputs like "X-SITE_B동 공급동" readable.
    return any(ord(char) > 127 for char in text) or all(byte < 128 for byte in data)


def _iter_dxf_pairs(file):
    while True:
        code = file.readline()
        if not code:
            return
        value = file.readline()
        if not value:
            return
        yield code.strip(), value.rstrip("\r\n")


def _read_block_pair(entity: dict, code: str, value: str) -> None:
    if code == "2":
        entity["name"] = value
    elif code == "3" and not entity.get("name"):
        entity["name"] = value
    elif code == "70":
        entity["flags"] = _to_int(value, default=0)
    elif code == "1":
        entity["xref_path"] = value


def _read_insert_pair(entity: dict, code: str, value: str) -> None:
    if code == "2":
        entity["name"] = value
    elif code == "10":
        entity["insert_x"] = _to_float(value, default=0.0)
    elif code == "20":
        entity["insert_y"] = _to_float(value, default=0.0)
    elif code == "30":
        entity["insert_z"] = _to_float(value, default=0.0)
    elif code == "41":
        entity["xscale"] = _to_float(value, default=1.0)
    elif code == "42":
        entity["yscale"] = _to_float(value, default=1.0)
    elif code == "43":
        entity["zscale"] = _to_float(value, default=1.0)
    elif code == "50":
        entity["rotation"] = _to_float(value, default=0.0)


def _xref_row(
    path: Path,
    root: Path,
    name: str,
    flags: int,
    xref_path: str,
    insert: dict | None,
    status: str,
) -> dict:
    insert = insert or {}
    return {
        "status": status,
        "drawing_path": str(path),
        "relative_drawing_path": str(path.relative_to(root)),
        "drawing_name": path.name,
        "xref_name": name,
        "xref_path": xref_path,
        "xref_file": Path(xref_path).name if xref_path else "",
        "floor_hint": _infer_floor(f"{name} {xref_path} {path.name}"),
        "is_external_reference": bool(flags & XREF_BLOCK_FLAG),
        "is_overlay_reference": bool(flags & XREF_OVERLAY_FLAG),
        "block_flags": flags,
        "insert_count": 1 if insert else 0,
        "insert_x": insert.get("insert_x", ""),
        "insert_y": insert.get("insert_y", ""),
        "insert_z": insert.get("insert_z", ""),
        "xscale": insert.get("xscale", ""),
        "yscale": insert.get("yscale", ""),
        "zscale": insert.get("zscale", ""),
        "rotation": insert.get("rotation", ""),
        "is_identity_insert": insert.get("is_identity_insert", ""),
    }


def _is_xref_block(name: str, flags: int, xref_path: str) -> bool:
    normalized = f"{name} {xref_path}".casefold()
    if flags & (XREF_BLOCK_FLAG | XREF_OVERLAY_FLAG):
        return True
    return bool(xref_path and ("xref" in normalized or "plan" in normalized or ".dwg" in normalized))


def _is_identity_insert(insert: dict) -> bool:
    return (
        math.isclose(float(insert["insert_x"]), 0.0, abs_tol=1e-6)
        and math.isclose(float(insert["insert_y"]), 0.0, abs_tol=1e-6)
        and math.isclose(float(insert["insert_z"]), 0.0, abs_tol=1e-6)
        and math.isclose(float(insert["xscale"]), 1.0, abs_tol=1e-9)
        and math.isclose(float(insert["yscale"]), 1.0, abs_tol=1e-9)
        and math.isclose(float(insert["zscale"]), 1.0, abs_tol=1e-9)
        and math.isclose(float(insert["rotation"]), 0.0, abs_tol=1e-9)
    )


def _infer_floor(text: str) -> str | None:
    patterns = [
        (re.compile(r"([1-6])\s*F", re.IGNORECASE), lambda match: f"{match.group(1)}F"),
        (re.compile(r"([1-6])\s*층"), lambda match: f"{match.group(1)}F"),
        (re.compile(r"X[-_]?([1-6])F[-_]?PLAN", re.IGNORECASE), lambda match: f"{match.group(1)}F"),
        (re.compile(r"XS[-_]?([1-6])F[-_]?PLAN", re.IGNORECASE), lambda match: f"{match.group(1)}F"),
        (re.compile(r"ROOF|RF|PH|옥탑|지붕", re.IGNORECASE), lambda match: "ROOF"),
        (re.compile(r"PIT", re.IGNORECASE), lambda match: "PIT"),
        (re.compile(r"SITE|배치", re.IGNORECASE), lambda match: "SITE"),
    ]
    for pattern, formatter in patterns:
        match = pattern.search(text)
        if match:
            return formatter(match)
    return None


def _to_float(value: str, default: float) -> float:
    try:
        return float(value)
    except ValueError:
        return default


def _to_int(value: str, default: int) -> int:
    try:
        return int(value)
    except ValueError:
        return default


def _write_csv(path: Path, rows: list[dict]) -> None:
    if rows:
        fieldnames = list(rows[0].keys())
    else:
        fieldnames = [
            "status",
            "drawing_path",
            "relative_drawing_path",
            "drawing_name",
            "xref_name",
            "xref_path",
            "xref_file",
            "floor_hint",
            "is_external_reference",
            "is_overlay_reference",
            "block_flags",
            "insert_count",
            "insert_x",
            "insert_y",
            "insert_z",
            "xscale",
            "yscale",
            "zscale",
            "rotation",
            "is_identity_insert",
        ]

    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
