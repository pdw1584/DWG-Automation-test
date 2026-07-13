from __future__ import annotations

from pathlib import Path
from typing import Protocol

from drawing_mapper.models import ParsedDrawing


class DrawingParser(Protocol):
    def parse(self, drawing_file_id: str, path: Path) -> ParsedDrawing:
        """Parse a drawing file into normalized drawing JSON."""

