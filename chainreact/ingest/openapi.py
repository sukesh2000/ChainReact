"""OpenAPI spec -> FieldDecl list (producer-side declarations)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from chainreact.contracts import FieldDecl

_UNITS = ("paise", "rupee", "cents", "dollar", "millisecond", "second", "meter")
_METHODS = ("get", "post", "put", "patch", "delete")


def _unit(schema: Dict[str, Any]) -> Optional[str]:
    if schema.get("x-unit"):
        return str(schema["x-unit"]).lower()
    desc = (schema.get("description") or "").lower()
    for u in _UNITS:
        if u in desc:
            return u
    return None


def _resolve(schema: Dict[str, Any], doc: Dict[str, Any], seen=()) -> Dict[str, Any]:
    ref = schema.get("$ref")
    if not ref:
        return schema
    if ref in seen or not ref.startswith("#/"):
        return {}
    node: Any = doc
    for part in ref[2:].split("/"):
        node = node.get(part, {})
    return _resolve(node, doc, seen + (ref,))


def _walk(schema, doc, prefix, service, endpoint, out, depth=0):
    schema = _resolve(schema, doc)
    t = schema.get("type", "object" if "properties" in schema else "unknown")
    if t == "object" and "properties" in schema and depth < 8:
        for name, sub in schema["properties"].items():
            _walk(sub, doc, f"{prefix}.{name}" if prefix else name, service, endpoint, out, depth + 1)
        return
    if t == "array" and depth < 8:
        items = _resolve(schema.get("items", {}), doc)
        if items.get("type") == "object" or "properties" in items:
            _walk(items, doc, f"{prefix}[]", service, endpoint, out, depth + 1)
            return
        t = f"array<{items.get('type', 'unknown')}>"
    if prefix:
        out.append(FieldDecl(
            service=service, endpoint=endpoint, name=prefix, type=t, format=schema.get("format"),
            nullable=bool(schema.get("nullable", False)),
            enum=[str(e) for e in schema["enum"]] if "enum" in schema else None, unit=_unit(schema)))


def parse_spec(path: Path, service: str) -> List[FieldDecl]:
    doc = yaml.safe_load(Path(path).read_text())
    out: List[FieldDecl] = []
    for p, item in (doc.get("paths") or {}).items():
        for m in _METHODS:
            op = (item or {}).get(m)
            if not op:
                continue
            for code, resp in (op.get("responses") or {}).items():
                if not str(code).startswith("2"):
                    continue
                schema = ((resp.get("content") or {}).get("application/json") or {}).get("schema")
                if schema:
                    _walk(schema, doc, "", service, f"{m.upper()} {p}", out)
    return out


def path_regex(spec_path: str) -> "re.Pattern[str]":
    """Match a normalized call path (params as '{}') against a spec path template."""
    parts = [r"[^/]+" if re.fullmatch(r"\{[^}]*\}", seg) else re.escape(seg) for seg in spec_path.split("/")]
    return re.compile("^" + "/".join(parts) + "/?$")
