from __future__ import annotations

import csv
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


COMMON_ODA_EXECUTABLES = [
    Path("C:/Program Files/ODA/ODAFileConverter/ODAFileConverter.exe"),
    Path("C:/Program Files/ODA/ODAFileConverter 27.1.0/ODAFileConverter.exe"),
    Path("C:/Program Files/ODA/ODAFileConverter 25.12.0/ODAFileConverter.exe"),
    Path("C:/Program Files/ODA/ODAFileConverter 25.8.0/ODAFileConverter.exe"),
    Path("C:/Program Files/ODA/ODAFileConverter 24.12.0/ODAFileConverter.exe"),
    Path("C:/Program Files (x86)/ODA/ODAFileConverter/ODAFileConverter.exe"),
]


@dataclass(frozen=True)
class ConversionFolder:
    drive_prefix: str
    input_dir: Path
    output_dir: Path
    dwg_count: int


def build_priority_conversion_plan(
    inventory_path: Path,
    raw_dir: Path,
    converted_dir: Path,
    priority_drive_path_prefixes: list[str],
) -> list[ConversionFolder]:
    inventory = _load_inventory(inventory_path)
    folders: dict[str, ConversionFolder] = {}

    # Converting all 2,187 DWGs is slow and noisy. The plan limits conversion
    # to selected design-document folders such as architecture/electrical/mechanical/telecom.
    for prefix in priority_drive_path_prefixes:
        matching = [
            item
            for item in inventory
            if (item.get("drive_path") or "").startswith(prefix) and item.get("local_path")
        ]
        if not matching:
            continue

        relative_prefix = Path(prefix.rstrip("/"))
        input_dir = raw_dir / relative_prefix
        output_dir = converted_dir / "dxf" / relative_prefix
        folders[prefix] = ConversionFolder(
            drive_prefix=prefix,
            input_dir=input_dir,
            output_dir=output_dir,
            dwg_count=len(matching),
        )

    return list(folders.values())


def write_conversion_plan(output_dir: Path, plan: list[ConversionFolder]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "dwg-conversion-plan.json"
    csv_path = output_dir / "dwg-conversion-plan.csv"

    rows = [
        {
            "drive_prefix": item.drive_prefix,
            "input_dir": str(item.input_dir),
            "output_dir": str(item.output_dir),
            "dwg_count": item.dwg_count,
        }
        for item in plan
    ]
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    with csv_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["drive_prefix", "input_dir", "output_dir", "dwg_count"])
        writer.writeheader()
        writer.writerows(rows)


def find_oda_executable(configured_path: str | None = None) -> Path | None:
    candidates = []
    if configured_path:
        candidates.append(Path(configured_path))
    candidates.extend(COMMON_ODA_EXECUTABLES)

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def build_oda_command(
    executable: Path,
    input_dir: Path,
    output_dir: Path,
    output_version: str,
    output_type: str,
    recurse: bool,
    audit: bool,
) -> list[str]:
    # ODAFileConverter CLI format:
    # input_dir output_dir output_version output_type recurse audit file_filter
    return [
        str(executable),
        str(input_dir),
        str(output_dir),
        output_version,
        output_type,
        "1" if recurse else "0",
        "1" if audit else "0",
        "*.DWG",
    ]


def run_oda_conversion(
    plan: list[ConversionFolder],
    executable: Path,
    output_version: str,
    output_type: str,
    recurse: bool,
    audit: bool,
    dry_run: bool,
) -> list[list[str]]:
    commands: list[list[str]] = []
    for item in plan:
        item.output_dir.mkdir(parents=True, exist_ok=True)
        # Commands are kept as argument lists so paths with spaces/Korean characters
        # are passed safely to subprocess.
        command = build_oda_command(
            executable=executable,
            input_dir=item.input_dir,
            output_dir=item.output_dir,
            output_version=output_version,
            output_type=output_type,
            recurse=recurse,
            audit=audit,
        )
        commands.append(command)
        if not dry_run:
            subprocess.run(command, check=True)
    return commands


def _load_inventory(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))
