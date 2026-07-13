from __future__ import annotations

from pathlib import Path

from drawing_mapper.models import DrawingPage, DrawingText, ParsedDrawing


class PdfParser:
    def parse(self, drawing_file_id: str, path: Path) -> ParsedDrawing:
        try:
            import fitz
        except ImportError as exc:
            message = "PDF parsing requires `pip install -e .[parser]`."
            raise RuntimeError(message) from exc

        document = fitz.open(path)
        pages: list[DrawingPage] = []

        for page_index, page in enumerate(document, start=1):
            texts: list[DrawingText] = []
            for block in page.get_text("blocks"):
                x0, y0, x1, y1, text, *_ = block
                value = str(text).strip()
                if not value:
                    continue
                texts.append(
                    DrawingText(
                        text=value,
                        x=float(x0),
                        y=float(y0),
                        width=float(x1 - x0),
                        height=float(y1 - y0),
                    )
                )

            rect = page.rect
            pages.append(
                DrawingPage(
                    page_number=page_index,
                    width=float(rect.width),
                    height=float(rect.height),
                    unit="pt",
                    texts=texts,
                )
            )

        return ParsedDrawing(
            drawing_file_id=drawing_file_id,
            source_path=str(path),
            source_format="pdf",
            pages=pages,
        )
