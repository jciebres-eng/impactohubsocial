"""Acesso à taxonomia (config/taxonomy.json) para validações simples."""
import json
from pathlib import Path

_TAX = json.loads((Path(__file__).resolve().parents[3] / "config" / "taxonomy.json").read_text(encoding="utf-8"))
PROFESSIONAL_CATEGORIES = set(_TAX["professional_categories"])
CAUSES = set(_TAX["causes"])
DOCUMENT_TYPES = _TAX["document_types"]
