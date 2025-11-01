from __future__ import annotations

import json
from typing import Any


def parse_metadata(text: str) -> dict[str, Any]:
    """JSON metnini sözlük olarak döndür."""

    stripped = text.strip()
    if not stripped:
        return {}
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Geçersiz JSON: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise ValueError("Metadata JSON bir sözlük olmalıdır")
    return value


def parse_document_lines(text: str) -> list[dict[str, Any]]:
    """Kullanıcı girişini belge listesine dönüştür."""

    documents: list[dict[str, Any]] = []
    for index, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 2:
            raise ValueError(
                f"Her satır en azından 'belge_id, skor' formatında olmalıdır (satır {index})"
            )
        document_id, score_text, *rest = parts
        try:
            score = float(score_text)
        except ValueError as exc:
            raise ValueError(f"Satır {index} için skor değeri sayısal olmalıdır") from exc
        metadata: dict[str, Any] = {}
        if rest:
            metadata["notes"] = ",".join(rest)
        documents.append({"document_id": document_id, "score": score, "metadata": metadata})
    return documents
