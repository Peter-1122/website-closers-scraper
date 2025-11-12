import json
from pathlib import Path
from typing import Any, List

class JsonExporter:
    def __init__(self, output_path: Path):
        self.output_path = output_path
        # Ensure parent directory exists
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, records: List[Any]) -> None:
        """
        Writes an array of records to JSON. Ensures UTF-8 and stable ordering of keys.
        """
        with self.output_path.open("w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2, sort_keys=False)