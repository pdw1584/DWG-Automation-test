from __future__ import annotations

import json
from pathlib import Path

from drawing_mapper.models import ParsedDrawing
from drawing_mapper.parsers.dxf_parser import DxfParser
from drawing_mapper.parsers.pdf_parser import PdfParser
from drawing_mapper.parsers.svg_parser import SvgParser


class DrawingParsePipeline:
    def __init__(self) -> None:
        self._parsers = {
            ".dxf": DxfParser(),
            ".pdf": PdfParser(),
            ".svg": SvgParser(),
        }

    def parse_raw_directory(self, raw_dir: Path, parsed_dir: Path) -> list[ParsedDrawing]:
        parsed_dir.mkdir(parents=True, exist_ok=True)
        results: list[ParsedDrawing] = []

        for path in sorted(raw_dir.rglob("*")):
            if not path.is_file():
                continue
            result = self.parse_file(path)
            results.append(result)
            output_path = _parsed_output_path(raw_dir, parsed_dir, path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")

        manifest_path = parsed_dir / "parse-manifest.json"
        manifest_path.write_text(
            json.dumps(
                [json.loads(result.model_dump_json()) for result in results],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return results

    def parse_file(self, path: Path) -> ParsedDrawing:
        suffix = path.suffix.lower()
        drawing_file_id = path.stem

        if suffix == ".dwg":
            return ParsedDrawing(
                drawing_file_id=drawing_file_id,
                source_path=str(path),
                source_format="dwg",
                status="conversion_required",
                message="DWG must be converted to DXF, PDF, or SVG before geometry parsing.",
            )

        parser = self._parsers.get(suffix)
        if not parser:
            return ParsedDrawing(
                drawing_file_id=drawing_file_id,
                source_path=str(path),
                source_format=suffix.removeprefix("."),
                status="skipped",
                message="Unsupported drawing file format.",
            )

        try:
            return parser.parse(drawing_file_id=drawing_file_id, path=path)
        except Exception as exc:
            return ParsedDrawing(
                drawing_file_id=drawing_file_id,
                source_path=str(path),
                source_format=suffix.removeprefix("."),
                status="failed",
                message=str(exc),
            )


def _parsed_output_path(raw_dir: Path, parsed_dir: Path, source_path: Path) -> Path:
    relative_path = source_path.relative_to(raw_dir)
    return parsed_dir / relative_path.with_suffix(relative_path.suffix + ".json")
