"""tree-sitter consumer scan: HTTP call sites -> ServiceEdges, and response field uses -> Beliefs."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

import tree_sitter_java as tsj
import tree_sitter_javascript as tsjs
import tree_sitter_python as tspy
from tree_sitter import Language, Node, Parser

from chainreact.contracts import Evidence

_LANGS = {
    ".py": Language(tspy.language()),
    ".js": Language(tsjs.language()),
    ".ts": Language(tsjs.language()),
    ".java": Language(tsj.language()),
}
_STRING_TYPES = {"string", "string_literal", "template_string"}
_URL = re.compile(r"https?://([A-Za-z0-9_-]+)(/[^\s\"'`?)]*)?")
_UNIT_HINT = re.compile(r"\b(paise|rupees?|cents|dollars?)\b", re.I)


class CallSite:
    def __init__(self, producer: str, path: str, var: Optional[str], line: int, snippet: str):
        self.producer, self.path, self.var, self.line, self.snippet = producer, path, var, line, snippet


class FieldUse:
    def __init__(self, var: str, field: str, line: int, snippet: str, unit: Optional[str]):
        self.var, self.field, self.line, self.snippet, self.unit = var, field, line, snippet, unit


def _text(n: Node) -> str:
    return n.text.decode("utf8", "replace")


def _walk(n: Node) -> Iterator[Node]:
    yield n
    for c in n.children:
        yield from _walk(c)


def _norm_path(p: str) -> str:
    return re.sub(r"\$\{[^}]*\}|\{[^}]*\}", "{}", p or "/")


def _lines(src: bytes) -> List[str]:
    return src.decode("utf8", "replace").splitlines()


def scan_file(path: Path) -> Tuple[List[CallSite], List[FieldUse]]:
    lang = _LANGS.get(path.suffix)
    if lang is None:
        return [], []
    src = path.read_bytes()
    lines = _lines(src)
    root = Parser(lang).parse(src).root_node
    calls: List[CallSite] = []
    for n in _walk(root):
        if n.type not in _STRING_TYPES:
            continue
        m = _URL.search(_text(n))
        if not m:
            continue
        # find the enclosing assignment/declaration binding the result to a variable
        var, p = None, n.parent
        while p is not None and p.type not in {"expression_statement", "program", "module", "block", "statement_block"}:
            if p.type in {"assignment", "variable_declarator", "local_variable_declaration"}:
                left = p.child_by_field_name("left") or p.child_by_field_name("name")
                if left is not None and left.type == "identifier":
                    var = _text(left)
                break
            p = p.parent
        ln = n.start_point[0]
        calls.append(CallSite(m.group(1), _norm_path(m.group(2)), var, ln + 1, lines[ln].strip()))

    uses: List[FieldUse] = []
    for n in _walk(root):
        var = field = None
        if n.type == "subscript":  # python: x["f"]
            v, idx = n.child_by_field_name("value"), n.child_by_field_name("subscript")
            if v is not None and v.type == "identifier" and idx is not None and idx.type == "string":
                var, field = _text(v), _text(idx).strip("\"'")
        elif n.type == "member_expression":  # js: x.f
            o, pr = n.child_by_field_name("object"), n.child_by_field_name("property")
            if o is not None and o.type == "identifier" and pr is not None:
                var, field = _text(o), _text(pr)
        if var and field:
            ln = n.start_point[0]
            h = _UNIT_HINT.search(lines[ln]) or (_UNIT_HINT.search(lines[ln - 1]) if False else None)
            uses.append(FieldUse(var, field, ln + 1, lines[ln].strip(), h.group(1).lower().rstrip("s") if h else None))
    return calls, uses


def evidence(repo: str, rel: str, line: int, snippet: str, conf: float = 1.0) -> Evidence:
    return Evidence(repo=repo, path=rel, line=line, snippet=snippet, source="ast", confidence=conf)
