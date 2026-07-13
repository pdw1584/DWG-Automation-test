from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree

from drawing_mapper.models import DrawingPage, DrawingText, ParsedDrawing


class SvgParser:
    def parse(self, drawing_file_id: str, path: Path) -> ParsedDrawing:
        tree = ElementTree.parse(path)
        root = tree.getroot()
        width = _float_attr(root, "width") or 0
        height = _float_attr(root, "height") or 0
        texts: list[DrawingText] = []

        for element in root.iter():
            if _local_name(element.tag) != "text":
                continue
            value = "".join(element.itertext()).strip()
            if not value:
                continue
            texts.append(
                DrawingText(
                    text=value,
                    x=_float_attr(element, "x") or 0,
                    y=_float_attr(element, "y") or 0,
                    width=0,
                    height=0,
                )
            )

        return ParsedDrawing(
            drawing_file_id=drawing_file_id,
            source_path=str(path),
            source_format="svg",
            pages=[DrawingPage(page_number=1, width=width, height=height, unit="svg", texts=texts)],
        )


def _float_attr(element: ElementTree.Element, name: str) -> float | None:
    raw = element.attrib.get(name)
    if not raw:
        return None
    numeric = "".join(char for char in raw if char.isdigit() or char in ".-")
    return float(numeric) if numeric else None


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
