from __future__ import annotations

import argparse
from pathlib import Path

from drawing_mapper.config import load_project_config
from drawing_mapper.conversion import (
    build_priority_conversion_plan,
    find_oda_executable,
    run_oda_conversion,
    write_conversion_plan,
)
from drawing_mapper.coordinate_basis import map_facility_coordinate_basis
from drawing_mapper.coordinate_calibration import apply_coordinate_calibration
from drawing_mapper.drive import GoogleDriveClient, LocalFixtureDriveClient, sync_drive_folder
from drawing_mapper.equipment import (
    extract_equipment_candidates_from_parsed_dir,
    load_equipment_keywords,
)
from drawing_mapper.final_export import export_auto_facility_locations, write_calibration_template
from drawing_mapper.filename_cleanup import remove_drive_id_prefixes
from drawing_mapper.inventory import build_dwg_inventory, summarize_inventory
from drawing_mapper.overlay import build_overlay_plan, collect_xr_plan_raw_drawings
from drawing_mapper.overlay_entities import extract_confirmed_overlay_entities
from drawing_mapper.parsers.pipeline import DrawingParsePipeline
from drawing_mapper.provisional_calibration import apply_provisional_anchor_calibration
from drawing_mapper.review import build_location_review_csv
from drawing_mapper.xref import build_xref_inventory


def main() -> None:
    parser = argparse.ArgumentParser(prog="drawing-mapper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    sync_parser = subparsers.add_parser("sync-drive", help="Download drawing files from Drive.")
    sync_parser.add_argument("--config", default="config/project.json")
    sync_parser.add_argument(
        "--local-fixture-dir",
        help="Use a local folder instead of Google Drive, for parser and pipeline testing.",
    )
    sync_parser.add_argument("--max-files", type=int, help="Limit files for a small sync test.")
    sync_parser.add_argument(
        "--list-only",
        action="store_true",
        help="Only write Drive metadata without downloading files.",
    )
    sync_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print folder scanning and download progress.",
    )

    parse_parser = subparsers.add_parser("parse-drawings", help="Parse raw drawings into JSON.")
    parse_parser.add_argument("--config", default="config/project.json")
    parse_parser.add_argument("--input-dir", help="Override drawing input directory.")
    parse_parser.add_argument("--output-dir", help="Override parsed JSON output directory.")

    inventory_parser = subparsers.add_parser(
        "build-inventory",
        help="Build DWG inventory with floor and discipline hints.",
    )
    inventory_parser.add_argument("--config", default="config/project.json")

    equipment_parser = subparsers.add_parser(
        "extract-equipment",
        help="Extract equipment candidates from parsed drawing JSON.",
    )
    equipment_parser.add_argument("--config", default="config/project.json")
    equipment_parser.add_argument("--input-dir", default="data/parsed/dxf/04_설계도서")
    equipment_parser.add_argument("--keywords", default="config/equipment-keywords.example.json")
    equipment_parser.add_argument("--output-dir", default="data/metadata")
    equipment_parser.add_argument("--include-architecture", action="store_true")

    conversion_parser = subparsers.add_parser(
        "convert-dwg",
        help="Convert priority DWG folders to DXF with ODA File Converter.",
    )
    conversion_parser.add_argument("--config", default="config/project.json")
    conversion_parser.add_argument("--dry-run", action="store_true")
    conversion_parser.add_argument(
        "--prefix",
        action="append",
        help="Override priority drive path prefix. Can be provided multiple times.",
    )

    review_parser = subparsers.add_parser(
        "build-review",
        help="Create a human-review CSV for facility location candidates.",
    )
    review_parser.add_argument(
        "--input",
        default="data/metadata/facility-location-high-confidence.csv",
        help="Facility location CSV to review.",
    )
    review_parser.add_argument(
        "--output",
        default="data/review/facility-location-review.csv",
        help="Review CSV output path.",
    )

    final_parser = subparsers.add_parser(
        "export-final",
        help="Export an interim final facility-location table without manual review.",
    )
    final_parser.add_argument("--config", default="config/project.json")
    final_parser.add_argument(
        "--input",
        default="data/metadata/facility-location-high-confidence.csv",
        help="Facility location CSV to export.",
    )
    final_parser.add_argument(
        "--output",
        default="data/final/facility-locations.csv",
        help="Final facility-location CSV output path.",
    )
    final_parser.add_argument(
        "--calibration-output",
        default="data/final/coordinate-calibration-template.csv",
        help="Coordinate calibration template output path.",
    )

    cleanup_parser = subparsers.add_parser(
        "remove-drive-id-prefixes",
        help="Remove Drive file id prefixes from local drawing filenames and generated data paths.",
    )
    cleanup_parser.add_argument("--config", default="config/project.json")
    cleanup_parser.add_argument(
        "--parsed-dir",
        default="data/parsed/dxf",
        help="Parsed drawing root to update.",
    )
    cleanup_parser.add_argument("--dry-run", action="store_true")

    calibration_parser = subparsers.add_parser(
        "apply-calibration",
        help="Apply floor coordinate calibration to final facility locations.",
    )
    calibration_parser.add_argument(
        "--locations",
        default="data/final/facility-locations.csv",
        help="Facility location CSV with drawing coordinates.",
    )
    calibration_parser.add_argument(
        "--calibration",
        default="data/final/coordinate-calibration-template.csv",
        help="Calibration CSV with floor control points.",
    )
    calibration_parser.add_argument(
        "--output",
        default="data/final/facility-locations-calibrated.csv",
        help="Output CSV with latitude and longitude populated.",
    )
    calibration_parser.add_argument(
        "--report",
        default="data/final/coordinate-calibration-report.json",
        help="Calibration report JSON output path.",
    )

    xref_parser = subparsers.add_parser(
        "build-xref-inventory",
        help="Build an XREF inventory from converted DXF files.",
    )
    xref_parser.add_argument("--input-dir", default="data/converted/dxf/04_설계도서")
    xref_parser.add_argument("--output-dir", default="data/metadata")

    basis_parser = subparsers.add_parser(
        "map-coordinate-basis",
        help="Attach common XREF coordinate-basis hints to facility locations.",
    )
    basis_parser.add_argument(
        "--locations",
        default="data/final/facility-locations.csv",
        help="Facility location CSV with drawing coordinates.",
    )
    basis_parser.add_argument(
        "--xref-inventory",
        default="data/metadata/xref-inventory.csv",
        help="XREF inventory CSV built from converted DXF files.",
    )
    basis_parser.add_argument(
        "--output",
        default="data/final/facility-locations-basis.csv",
        help="Output CSV with basis coordinates and XREF metadata.",
    )
    basis_parser.add_argument(
        "--report",
        default="data/final/coordinate-basis-report.json",
        help="Coordinate-basis mapping report JSON.",
    )

    provisional_parser = subparsers.add_parser(
        "apply-provisional-anchor",
        help="Create rough GPS estimates from one drawing/GPS anchor point.",
    )
    provisional_parser.add_argument(
        "--locations",
        default="data/final/facility-locations-basis.csv",
        help="Facility location CSV, preferably with basis_x and basis_y.",
    )
    provisional_parser.add_argument("--anchor-x", type=float, required=True)
    provisional_parser.add_argument("--anchor-y", type=float, required=True)
    provisional_parser.add_argument("--anchor-latitude", type=float, required=True)
    provisional_parser.add_argument("--anchor-longitude", type=float, required=True)
    provisional_parser.add_argument(
        "--unit",
        default="mm",
        choices=["mm", "cm", "m"],
        help="Drawing coordinate unit assumption.",
    )
    provisional_parser.add_argument(
        "--rotation-degrees",
        type=float,
        default=0.0,
        help="Manual clockwise rotation from drawing axes to east/north axes.",
    )
    provisional_parser.add_argument(
        "--output",
        default="data/final/facility-locations-provisional.csv",
        help="Output CSV with provisional latitude and longitude.",
    )
    provisional_parser.add_argument(
        "--report",
        default="data/final/provisional-calibration-report.json",
        help="Provisional calibration report JSON.",
    )
    provisional_parser.add_argument(
        "--kml-output",
        default="data/final/facility-locations-provisional.kml",
        help="Optional KML output for Google Earth. Use an empty value to skip.",
    )

    overlay_parser = subparsers.add_parser(
        "build-overlay-plan",
        help="Build drawing overlay groups from plan-like XREF references.",
    )
    overlay_parser.add_argument(
        "--xref-inventory",
        default="data/legacy/metadata/xref-inventory.csv",
        help="XREF inventory CSV.",
    )
    overlay_parser.add_argument(
        "--facility-locations",
        default="data/legacy/metadata/facility-location-high-confidence.csv",
        help="Facility location CSV used to count equipment per drawing.",
    )
    overlay_parser.add_argument(
        "--output-dir",
        default="data/overlay",
        help="Directory for overlay plan outputs.",
    )

    collect_xr_parser = subparsers.add_parser(
        "collect-xr-plan-raw",
        help="Copy RAW DWG files that reference XR-PLAN into a v2 review folder.",
    )
    collect_xr_parser.add_argument(
        "--overlay-drawings",
        default="data/overlay/drawing-overlay-drawings.csv",
        help="Overlay drawing CSV generated by build-overlay-plan.",
    )
    collect_xr_parser.add_argument(
        "--raw-root",
        default="data/raw",
        help="RAW drawing root.",
    )
    collect_xr_parser.add_argument(
        "--output-dir",
        default="data/overlay/v2",
        help="Output directory for copied RAW drawings and manifest.",
    )
    collect_xr_parser.add_argument(
        "--priority",
        default="",
        help="Optional overlay priority filter, e.g. A_XR_PLAN_IDENTITY.",
    )
    collect_xr_parser.add_argument("--dry-run", action="store_true")

    overlay_entities_parser = subparsers.add_parser(
        "extract-overlay-entities",
        help="Extract common-basis entities from confirmed XR-PLAN overlay DXF drawings.",
    )
    overlay_entities_parser.add_argument(
        "--confirmed-drawings",
        default="v2/xr-plan-confirmed-drawings.csv",
        help="Confirmed XR-PLAN drawing list CSV.",
    )
    overlay_entities_parser.add_argument(
        "--output",
        default="v2/extracted-overlay-entities.csv",
        help="Output entity CSV.",
    )
    overlay_entities_parser.add_argument(
        "--report",
        default="v2/extracted-overlay-entities-report.json",
        help="Extraction report JSON.",
    )

    args = parser.parse_args()
    if args.command == "sync-drive":
        sync_drive_command(
            config_path=Path(args.config),
            local_fixture_dir=args.local_fixture_dir,
            max_files=args.max_files,
            list_only=args.list_only,
            verbose=args.verbose,
        )
    elif args.command == "parse-drawings":
        parse_drawings_command(
            config_path=Path(args.config),
            input_dir=Path(args.input_dir) if args.input_dir else None,
            output_dir=Path(args.output_dir) if args.output_dir else None,
        )
    elif args.command == "build-inventory":
        build_inventory_command(Path(args.config))
    elif args.command == "extract-equipment":
        extract_equipment_command(
            config_path=Path(args.config),
            input_dir=Path(args.input_dir),
            keywords_path=Path(args.keywords),
            output_dir=Path(args.output_dir),
            include_architecture=args.include_architecture,
        )
    elif args.command == "convert-dwg":
        convert_dwg_command(Path(args.config), dry_run=args.dry_run, prefixes=args.prefix)
    elif args.command == "build-review":
        build_review_command(input_path=Path(args.input), output_path=Path(args.output))
    elif args.command == "export-final":
        export_final_command(
            config_path=Path(args.config),
            input_path=Path(args.input),
            output_path=Path(args.output),
            calibration_output_path=Path(args.calibration_output),
        )
    elif args.command == "remove-drive-id-prefixes":
        remove_drive_id_prefixes_command(
            config_path=Path(args.config),
            parsed_dir=Path(args.parsed_dir),
            dry_run=args.dry_run,
        )
    elif args.command == "apply-calibration":
        apply_calibration_command(
            locations_path=Path(args.locations),
            calibration_path=Path(args.calibration),
            output_path=Path(args.output),
            report_path=Path(args.report),
        )
    elif args.command == "build-xref-inventory":
        build_xref_inventory_command(
            input_dir=Path(args.input_dir),
            output_dir=Path(args.output_dir),
        )
    elif args.command == "map-coordinate-basis":
        map_coordinate_basis_command(
            locations_path=Path(args.locations),
            xref_inventory_path=Path(args.xref_inventory),
            output_path=Path(args.output),
            report_path=Path(args.report),
        )
    elif args.command == "apply-provisional-anchor":
        apply_provisional_anchor_command(
            locations_path=Path(args.locations),
            output_path=Path(args.output),
            report_path=Path(args.report),
            anchor_x=args.anchor_x,
            anchor_y=args.anchor_y,
            anchor_latitude=args.anchor_latitude,
            anchor_longitude=args.anchor_longitude,
            unit=args.unit,
            rotation_degrees=args.rotation_degrees,
            kml_output_path=Path(args.kml_output) if args.kml_output else None,
        )
    elif args.command == "build-overlay-plan":
        build_overlay_plan_command(
            xref_inventory_path=Path(args.xref_inventory),
            facility_locations_path=Path(args.facility_locations)
            if args.facility_locations
            else None,
            output_dir=Path(args.output_dir),
        )
    elif args.command == "collect-xr-plan-raw":
        collect_xr_plan_raw_command(
            overlay_drawings_path=Path(args.overlay_drawings),
            raw_root=Path(args.raw_root),
            output_dir=Path(args.output_dir),
            priority=args.priority or None,
            dry_run=args.dry_run,
        )
    elif args.command == "extract-overlay-entities":
        extract_overlay_entities_command(
            confirmed_drawings_path=Path(args.confirmed_drawings),
            output_path=Path(args.output),
            report_path=Path(args.report),
        )


def sync_drive_command(
    config_path: Path,
    local_fixture_dir: str | None = None,
    max_files: int | None = None,
    list_only: bool = False,
    verbose: bool = False,
) -> None:
    config = load_project_config(config_path)

    if local_fixture_dir:
        client = LocalFixtureDriveClient(Path(local_fixture_dir))
    else:
        service_account_file = config.google_drive.service_account_file
        if not service_account_file:
            raise SystemExit(
                "`google_drive.service_account_file` is required unless --local-fixture-dir is used."
            )
        client = GoogleDriveClient(
            service_account_file=Path(service_account_file),
            include_shared_drives=config.google_drive.include_shared_drives,
        )

    files = sync_drive_folder(
        client=client,
        folder_id=config.google_drive.folder_id,
        allowed_mime_types=config.google_drive.allowed_mime_types,
        allowed_extensions=config.google_drive.allowed_extensions,
        excluded_folder_name_contains=config.google_drive.excluded_folder_name_contains,
        excluded_folder_names=config.google_drive.excluded_folder_names,
        recursive=config.google_drive.recursive,
        preserve_drive_paths=config.google_drive.preserve_drive_paths,
        raw_dir=Path(config.storage.raw_dir),
        metadata_dir=Path(config.storage.metadata_dir),
        max_files=max_files,
        list_only=list_only,
        progress=_print_progress if verbose else None,
    )

    action = "Found" if list_only else "Synced"
    print(f"{action} {len(files)} drawing file(s).")
    for file in files:
        print(f"- {file.name} ({file.mime_type})")


def _print_progress(message: str) -> None:
    print(f"[sync] {message}", flush=True)


def parse_drawings_command(
    config_path: Path,
    input_dir: Path | None = None,
    output_dir: Path | None = None,
) -> None:
    config = load_project_config(config_path)
    pipeline = DrawingParsePipeline()
    results = pipeline.parse_raw_directory(
        raw_dir=input_dir or Path(config.storage.raw_dir),
        parsed_dir=output_dir or Path(config.storage.parsed_dir),
    )

    counts: dict[str, int] = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1

    print(f"Processed {len(results)} drawing file(s).")
    for status, count in sorted(counts.items()):
        print(f"- {status}: {count}")


def build_inventory_command(config_path: Path) -> None:
    config = load_project_config(config_path)
    metadata_dir = Path(config.storage.metadata_dir)
    inventory = build_dwg_inventory(
        metadata_path=metadata_dir / "drive-files.json",
        raw_dir=Path(config.storage.raw_dir),
        output_dir=metadata_dir,
        allowed_floor_levels=config.building.floors,
    )
    summary = summarize_inventory(inventory)

    print(f"Built inventory for {len(inventory)} DWG file(s).")
    print(f"- output json: {metadata_dir / 'dwg-inventory.json'}")
    print(f"- output csv: {metadata_dir / 'dwg-inventory.csv'}")
    for group, counts in summary.items():
        print(f"\n[{group}]")
        for key, count in counts.items():
            print(f"- {key}: {count}")


def convert_dwg_command(config_path: Path, dry_run: bool, prefixes: list[str] | None = None) -> None:
    config = load_project_config(config_path)
    metadata_dir = Path(config.storage.metadata_dir)
    raw_dir = Path(config.storage.raw_dir)
    converted_dir = Path(config.storage.converted_dir)

    plan = build_priority_conversion_plan(
        inventory_path=metadata_dir / "dwg-inventory.json",
        raw_dir=raw_dir,
        converted_dir=converted_dir,
        priority_drive_path_prefixes=prefixes or config.dwg_conversion.priority_drive_path_prefixes,
    )
    write_conversion_plan(metadata_dir, plan)

    print(f"Prepared {len(plan)} priority conversion folder(s).")
    for item in plan:
        print(f"- {item.drive_prefix}: {item.dwg_count} DWG")

    executable = find_oda_executable(config.dwg_conversion.oda_executable)
    if not executable:
        print("\nODA File Converter executable was not found.")
        print("Set `dwg_conversion.oda_executable` in config/project.json.")
        return

    commands = run_oda_conversion(
        plan=plan,
        executable=executable,
        output_version=config.dwg_conversion.output_version,
        output_type=config.dwg_conversion.output_type,
        recurse=config.dwg_conversion.recurse,
        audit=config.dwg_conversion.audit,
        dry_run=dry_run,
    )

    action = "Planned" if dry_run else "Ran"
    print(f"\n{action} {len(commands)} ODA conversion command(s).")
    for command in commands:
        print(" ".join(f'"{part}"' if " " in part else part for part in command))


def extract_equipment_command(
    config_path: Path,
    input_dir: Path,
    keywords_path: Path,
    output_dir: Path,
    include_architecture: bool = False,
) -> None:
    config = load_project_config(config_path)
    keywords = load_equipment_keywords(keywords_path)
    candidates = extract_equipment_candidates_from_parsed_dir(
        parsed_dir=input_dir,
        keywords=keywords,
        output_dir=output_dir,
        allowed_floor_levels=config.building.floors,
        include_architecture=include_architecture,
    )
    print(f"Extracted {len(candidates)} equipment candidate(s).")
    print(f"- output json: {output_dir / 'equipment-candidates.json'}")
    print(f"- output csv: {output_dir / 'equipment-candidates.csv'}")


def build_review_command(input_path: Path, output_path: Path) -> None:
    rows = build_location_review_csv(input_path=input_path, output_path=output_path)
    print(f"Built review CSV with {len(rows)} row(s).")
    print(f"- input csv: {input_path}")
    print(f"- output csv: {output_path}")


def export_final_command(
    config_path: Path,
    input_path: Path,
    output_path: Path,
    calibration_output_path: Path,
) -> None:
    config = load_project_config(config_path)
    locations = export_auto_facility_locations(
        input_path=input_path,
        output_path=output_path,
        building_name=config.building.name,
        building_address=config.building.address,
    )
    calibration_rows = write_calibration_template(
        output_path=calibration_output_path,
        floors=config.building.floors,
        extra_floor_labels=sorted({str(location.get("floor") or "") for location in locations}),
    )
    print(f"Exported {len(locations)} interim facility location(s).")
    print(f"- output csv: {output_path}")
    print(f"Built {len(calibration_rows)} calibration template row(s).")
    print(f"- calibration csv: {calibration_output_path}")


def remove_drive_id_prefixes_command(
    config_path: Path,
    parsed_dir: Path,
    dry_run: bool,
) -> None:
    config = load_project_config(config_path)
    metadata_dir = Path(config.storage.metadata_dir)
    result = remove_drive_id_prefixes(
        metadata_path=metadata_dir / "drive-files.json",
        raw_dir=Path(config.storage.raw_dir),
        converted_dir=Path(config.storage.converted_dir),
        parsed_dir=parsed_dir,
        data_dirs=[
            Path(config.storage.metadata_dir),
            Path("data/review"),
            Path("data/final"),
            parsed_dir,
        ],
        report_dir=metadata_dir,
        dry_run=dry_run,
    )

    action = "Planned" if dry_run else "Renamed"
    print(f"{action} {len(result.renamed)} file(s).")
    print(f"- skipped conflicts: {len(result.skipped)}")
    print(f"- updated text files: {len(result.updated_text_files)}")
    print(f"- skipped locked text files: {len(result.skipped_text_files)}")
    print(f"- report dir: {metadata_dir}")


def apply_calibration_command(
    locations_path: Path,
    calibration_path: Path,
    output_path: Path,
    report_path: Path,
) -> None:
    report = apply_coordinate_calibration(
        locations_path=locations_path,
        calibration_path=calibration_path,
        output_path=output_path,
        report_path=report_path,
    )
    print(f"Applied {report['transform_count']} floor calibration transform(s).")
    print(f"- calibrated locations: {report['calibrated_count']}")
    print(f"- skipped locations: {report['skipped_count']}")
    print(f"- output csv: {output_path}")
    print(f"- report json: {report_path}")


def build_xref_inventory_command(input_dir: Path, output_dir: Path) -> None:
    rows = build_xref_inventory(input_dir=input_dir, output_dir=output_dir)
    failed = sum(1 for row in rows if row.get("status") == "failed")
    identity = sum(1 for row in rows if row.get("is_identity_insert") is True)
    print(f"Built XREF inventory with {len(rows)} row(s).")
    print(f"- identity inserts: {identity}")
    print(f"- failed drawings: {failed}")
    print(f"- output csv: {output_dir / 'xref-inventory.csv'}")
    print(f"- summary csv: {output_dir / 'xref-summary.csv'}")
    print(f"- plan candidates csv: {output_dir / 'xref-plan-candidates.csv'}")


def map_coordinate_basis_command(
    locations_path: Path,
    xref_inventory_path: Path,
    output_path: Path,
    report_path: Path,
) -> None:
    report = map_facility_coordinate_basis(
        locations_path=locations_path,
        xref_inventory_path=xref_inventory_path,
        output_path=output_path,
        report_path=report_path,
    )
    print(f"Mapped coordinate basis for {report['mapped_count']} location(s).")
    print(f"- unmapped locations: {report['unmapped_count']}")
    print(f"- output csv: {output_path}")
    print(f"- report json: {report_path}")


def apply_provisional_anchor_command(
    locations_path: Path,
    output_path: Path,
    report_path: Path,
    anchor_x: float,
    anchor_y: float,
    anchor_latitude: float,
    anchor_longitude: float,
    unit: str,
    rotation_degrees: float,
    kml_output_path: Path | None,
) -> None:
    report = apply_provisional_anchor_calibration(
        locations_path=locations_path,
        output_path=output_path,
        report_path=report_path,
        anchor_x=anchor_x,
        anchor_y=anchor_y,
        anchor_latitude=anchor_latitude,
        anchor_longitude=anchor_longitude,
        unit=unit,
        rotation_degrees=rotation_degrees,
        kml_output_path=kml_output_path,
    )
    print(f"Created provisional GPS estimates for {report['calibrated_count']} location(s).")
    print(f"- skipped locations: {report['skipped_count']}")
    print(f"- output csv: {output_path}")
    if kml_output_path:
        print(f"- output kml: {kml_output_path}")
    print(f"- report json: {report_path}")


def build_overlay_plan_command(
    xref_inventory_path: Path,
    facility_locations_path: Path | None,
    output_dir: Path,
) -> None:
    report = build_overlay_plan(
        xref_inventory_path=xref_inventory_path,
        facility_locations_path=facility_locations_path,
        output_dir=output_dir,
    )
    print(f"Built {report['overlay_group_count']} overlay group(s).")
    print(f"- overlay drawings: {report['overlay_drawing_count']}")
    print(f"- identity groups: {report['identity_group_count']}")
    print(f"- output dir: {output_dir}")


def collect_xr_plan_raw_command(
    overlay_drawings_path: Path,
    raw_root: Path,
    output_dir: Path,
    priority: str | None,
    dry_run: bool,
) -> None:
    report = collect_xr_plan_raw_drawings(
        overlay_drawings_path=overlay_drawings_path,
        raw_root=raw_root,
        output_dir=output_dir,
        priority=priority,
        dry_run=dry_run,
    )
    action = "Planned" if dry_run else "Copied"
    print(f"{action} {report['copied_count'] or report['planned_count']} XR-PLAN RAW drawing(s).")
    print(f"- selected drawings: {report['selected_count']}")
    print(f"- missing raw files: {report['missing_count']}")
    print(f"- output raw dir: {report['output_raw_dir']}")
    print(f"- manifest csv: {report['manifest_csv']}")


def extract_overlay_entities_command(
    confirmed_drawings_path: Path,
    output_path: Path,
    report_path: Path,
) -> None:
    report = extract_confirmed_overlay_entities(
        confirmed_drawings_path=confirmed_drawings_path,
        output_csv_path=output_path,
        report_path=report_path,
    )
    print(f"Extracted {report['entity_count']} overlay entity row(s).")
    print(f"- parsed drawings: {report['parsed_drawing_count']}")
    print(f"- skipped drawings: {report['skipped_drawing_count']}")
    print(f"- failed drawings: {report['failed_drawing_count']}")
    print(f"- output csv: {output_path}")
    print(f"- report json: {report_path}")


if __name__ == "__main__":
    main()
