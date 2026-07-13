from __future__ import annotations

from pathlib import Path

from drawing_mapper.models import DrawingPage, DrawingPath, DrawingText, ParsedDrawing


class DxfParser:
    def parse(self, drawing_file_id: str, path: Path) -> ParsedDrawing:
        try:
            import ezdxf
        except ImportError as exc:
            message = "DXF parsing requires `pip install -e .[parser]`."
            raise RuntimeError(message) from exc

        document = ezdxf.readfile(path)
        modelspace = document.modelspace()
        texts: list[DrawingText] = []
        paths: list[DrawingPath] = []
        min_x: float | None = None
        min_y: float | None = None
        max_x: float | None = None
        max_y: float | None = None

        for entity in modelspace:
            entity_type = entity.dxftype()
            layer = getattr(entity.dxf, "layer", None)

            if entity_type in {"TEXT", "MTEXT"}:
                text, x, y = _extract_text(entity, entity_type)
                if text:
                    texts.append(DrawingText(text=text, x=x, y=y, width=0, height=0))
                    min_x, min_y, max_x, max_y = _extend_bounds(min_x, min_y, max_x, max_y, x, y)
                continue

            bbox = _entity_bbox(entity)
            if bbox:
                min_x, min_y, max_x, max_y = _extend_bounds(
                    min_x,
                    min_y,
                    max_x,
                    max_y,
                    bbox[0],
                    bbox[1],
                    bbox[2],
                    bbox[3],
                )

            paths.append(
                DrawingPath(
                    d=entity_type,
                    bbox=bbox,
                    layer=layer,
                    entity_type=entity_type,
                )
            )

        width = (max_x - min_x) if min_x is not None and max_x is not None else 0
        height = (max_y - min_y) if min_y is not None and max_y is not None else 0
        page = DrawingPage(page_number=1, width=width, height=height, unit="dxf", texts=texts, paths=paths)

        return ParsedDrawing(
            drawing_file_id=drawing_file_id,
            source_path=str(path),
            source_format="dxf",
            pages=[page],
        )


def _extract_text(entity: object, entity_type: str) -> tuple[str, float, float]:
    if entity_type == "MTEXT":
        text = entity.plain_text()
        insert = entity.dxf.insert
    else:
        text = entity.dxf.text
        insert = entity.dxf.insert
    return text.strip(), float(insert.x), float(insert.y)


def _entity_bbox(entity: object) -> tuple[float, float, float, float] | None:
    try:
        extmin, extmax = entity.bbox()
    except Exception:
        return None
    return (float(extmin.x), float(extmin.y), float(extmax.x), float(extmax.y))


def _extend_bounds(
    min_x: float | None,
    min_y: float | None,
    max_x: float | None,
    max_y: float | None,
    x1: float,
    y1: float,
    x2: float | None = None,
    y2: float | None = None,
) -> tuple[float, float, float, float]:
    x2 = x1 if x2 is None else x2
    y2 = y1 if y2 is None else y2
    return (
        min(x1, x2) if min_x is None else min(min_x, x1, x2),
        min(y1, y2) if min_y is None else min(min_y, y1, y2),
        max(x1, x2) if max_x is None else max(max_x, x1, x2),
        max(y1, y2) if max_y is None else max(max_y, y1, y2),
    )
