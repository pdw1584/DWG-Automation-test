from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path


TEXT_SUFFIXES = {".csv", ".json", ".md", ".txt"}


@dataclass(frozen=True)
class CleanupResult:
    renamed: list[dict]
    skipped: list[dict]
    updated_text_files: list[str]
    skipped_text_files: list[dict]


def remove_drive_id_prefixes(
    metadata_path: Path,
    raw_dir: Path,
    converted_dir: Path,
    parsed_dir: Path,
    data_dirs: list[Path],
    report_dir: Path,
    dry_run: bool = False,
) -> CleanupResult:
    drive_files = _load_drive_files(metadata_path)
    rename_pairs = _build_rename_pairs(drive_files)
    rename_actions = _build_rename_actions(
        drive_files=drive_files,
        raw_dir=raw_dir,
        converted_dir=converted_dir,
        parsed_dir=parsed_dir,
    )

    renamed: list[dict] = []
    skipped: list[dict] = []
    for source, target, kind in rename_actions:
        if not source.exists():
            continue
        if target.exists():
            skipped.append(
                {
                    "kind": kind,
                    "source": str(source),
                    "target": str(target),
                    "reason": "target_exists",
                }
            )
            continue

        renamed.append({"kind": kind, "source": str(source), "target": str(target)})
        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            source.rename(target)

    updated_text_files, skipped_text_files = _replace_in_text_files(
        data_dirs,
        rename_pairs,
        dry_run=dry_run,
    )
    _write_report(
        report_dir=report_dir,
        renamed=renamed,
        skipped=skipped,
        updated_text_files=updated_text_files,
        skipped_text_files=skipped_text_files,
        dry_run=dry_run,
    )
    return CleanupResult(
        renamed=renamed,
        skipped=skipped,
        updated_text_files=updated_text_files,
        skipped_text_files=skipped_text_files,
    )


def _load_drive_files(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _build_rename_pairs(drive_files: list[dict]) -> list[tuple[str, str]]:
    pairs = []
    for file in drive_files:
        file_id = str(file.get("id") or "")
        name = str(file.get("name") or "")
        if not file_id or not name:
            continue

        safe_id = _safe_filename(file_id)
        safe_name = _safe_filename(name)
        stem = Path(safe_name).stem
        suffix = Path(safe_name).suffix
        prefixed_name = f"{safe_id}_{safe_name}"
        pairs.append((prefixed_name, safe_name))
        pairs.append((f"{safe_id}_{stem}", stem))

        if suffix.casefold() == ".dwg":
            pairs.append((f"{safe_id}_{stem}.dxf.json", f"{stem}.dxf.json"))
            pairs.append((f"{safe_id}_{stem}.dxf", f"{stem}.dxf"))
            pairs.append((f"{safe_id}_{stem}.DWG", f"{stem}.DWG"))

    # Longer strings first prevents partial replacements when names overlap.
    return sorted(set(pairs), key=lambda pair: len(pair[0]), reverse=True)


def _build_rename_actions(
    drive_files: list[dict],
    raw_dir: Path,
    converted_dir: Path,
    parsed_dir: Path,
) -> list[tuple[Path, Path, str]]:
    actions = []
    for file in drive_files:
        file_id = str(file.get("id") or "")
        name = str(file.get("name") or "")
        drive_path = str(file.get("drive_path") or name)
        if not file_id or not name:
            continue

        relative_folder = Path(drive_path).parent
        if str(relative_folder) == ".":
            relative_folder = Path()

        safe_id = _safe_filename(file_id)
        safe_name = _safe_filename(name)
        safe_stem = Path(safe_name).stem
        raw_source = raw_dir / relative_folder / f"{safe_id}_{safe_name}"
        raw_target = raw_dir / relative_folder / safe_name
        actions.append((raw_source, raw_target, "raw"))

        if Path(safe_name).suffix.casefold() == ".dwg":
            converted_source = converted_dir / "dxf" / relative_folder / f"{safe_id}_{safe_stem}.dxf"
            converted_target = converted_dir / "dxf" / relative_folder / f"{safe_stem}.dxf"
            actions.append((converted_source, converted_target, "converted"))

            parsed_source = parsed_dir / relative_folder / f"{safe_id}_{safe_stem}.dxf.json"
            parsed_target = parsed_dir / relative_folder / f"{safe_stem}.dxf.json"
            actions.append((parsed_source, parsed_target, "parsed"))

    return actions


def _replace_in_text_files(
    data_dirs: list[Path],
    rename_pairs: list[tuple[str, str]],
    dry_run: bool,
) -> tuple[list[str], list[dict]]:
    updated = []
    skipped = []
    replacement_chunks = _build_replacement_chunks(rename_pairs, chunk_size=300)
    for data_dir in data_dirs:
        if not data_dir.exists():
            continue
        for path in sorted(data_dir.rglob("*")):
            if not path.is_file() or path.suffix.casefold() not in TEXT_SUFFIXES:
                continue

            try:
                original = path.read_text(encoding="utf-8-sig")
            except PermissionError:
                skipped.append({"path": str(path), "reason": "read_permission_denied"})
                continue

            changed = original
            for pattern, replacements in replacement_chunks:
                changed = pattern.sub(lambda match: replacements[match.group(0)], changed)
            if changed == original:
                continue

            updated.append(str(path))
            if not dry_run:
                try:
                    path.write_text(changed, encoding="utf-8-sig")
                except PermissionError:
                    updated.pop()
                    skipped.append({"path": str(path), "reason": "write_permission_denied"})

    return updated, skipped


def _build_replacement_chunks(
    rename_pairs: list[tuple[str, str]],
    chunk_size: int,
) -> list[tuple[re.Pattern[str], dict[str, str]]]:
    chunks = []
    for index in range(0, len(rename_pairs), chunk_size):
        chunk = rename_pairs[index : index + chunk_size]
        replacements = dict(chunk)
        pattern = re.compile("|".join(re.escape(old) for old, _ in chunk))
        chunks.append((pattern, replacements))
    return chunks


def _write_report(
    report_dir: Path,
    renamed: list[dict],
    skipped: list[dict],
    updated_text_files: list[str],
    skipped_text_files: list[dict],
    dry_run: bool,
) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    prefix = "drive-id-cleanup-dry-run" if dry_run else "drive-id-cleanup"
    json_path = report_dir / f"{prefix}.json"
    csv_path = report_dir / f"{prefix}-renamed.csv"
    skipped_csv_path = report_dir / f"{prefix}-skipped.csv"

    json_path.write_text(
        json.dumps(
            {
                "dry_run": dry_run,
                "renamed_count": len(renamed),
                "skipped_count": len(skipped),
                "updated_text_file_count": len(updated_text_files),
                "skipped_text_file_count": len(skipped_text_files),
                "renamed": renamed,
                "skipped": skipped,
                "updated_text_files": updated_text_files,
                "skipped_text_files": skipped_text_files,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    _write_csv(csv_path, ["kind", "source", "target"], renamed)
    _write_csv(skipped_csv_path, ["kind", "source", "target", "reason"], skipped)


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _safe_filename(name: str) -> str:
    blocked = '<>:"/\\|?*'
    safe = "".join("_" if char in blocked else char for char in name).strip()
    return safe or "unnamed-drawing"
