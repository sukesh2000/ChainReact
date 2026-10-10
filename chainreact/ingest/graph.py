"""Registry + ingest orchestration -> BeliefGraph."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Set

import yaml

from chainreact.contracts import Belief, BeliefGraph, FieldDecl, ServiceEdge
from .consumer import evidence, scan_file
from .openapi import parse_spec, path_regex

_SKIP = {".git", "node_modules", ".venv", "__pycache__", "target", "build"}


def load_registry(path: Path) -> dict:
    """chainreact.yaml: services: {name: {path: <dir>, spec: <file, optional>}}, edges: [{consumer, producer}]"""
    reg = yaml.safe_load(Path(path).read_text())
    base = Path(path).parent
    for s in reg["services"].values():
        s["path"] = (base / s["path"]).resolve()
    reg.setdefault("edges", [])
    return reg


def _source_files(root: Path):
    for p in sorted(root.rglob("*")):
        if p.is_file() and not (set(p.relative_to(root).parts) & _SKIP):
            yield p


def build_graph(registry_path: Path) -> BeliefGraph:
    reg = load_registry(registry_path)
    services: Dict[str, dict] = reg["services"]
    decls: List[FieldDecl] = []
    for name, s in services.items():
        if s.get("spec"):
            decls += parse_spec(s["path"] / s["spec"], name)
    endpoints = {}  # producer -> [(regex, "GET /x")]
    for d in decls:
        method, spec_path = d.endpoint.split(" ", 1)
        endpoints.setdefault(d.service, {})[d.endpoint] = path_regex(spec_path)

    declared = {(e["consumer"], e["producer"]) for e in reg["edges"]}
    edges: Dict[tuple, ServiceEdge] = {}
    beliefs: List[Belief] = []
    for consumer, s in services.items():
        for f in _source_files(s["path"]):
            calls, uses = scan_file(f)
            rel = str(f.relative_to(s["path"]))
            for c in calls:
                if c.producer not in services or c.producer == consumer:
                    continue
                key = (consumer, c.producer)
                ev = evidence(consumer, rel, c.line, c.snippet)
                if key in edges:
                    edges[key] = edges[key].model_copy(update={"evidence": edges[key].evidence + [ev]})
                else:
                    edges[key] = ServiceEdge(consumer=consumer, producer=c.producer, declared=key in declared, evidence=[ev])
                ep = next((e for e, rx in sorted(endpoints.get(c.producer, {}).items()) if rx.match(c.path)), None)
                if not (ep and c.var):
                    continue
                for u in uses:
                    if u.var == c.var and u.line >= c.line:
                        beliefs.append(Belief(
                            consumer=consumer, producer=c.producer, endpoint=ep, field=u.field,
                            assumed_unit=u.unit,
                            evidence=[evidence(consumer, rel, u.line, u.snippet, 0.6 if u.unit else 1.0)]))
    for key in declared - set(edges):  # declared but never observed in code
        edges[key] = ServiceEdge(consumer=key[0], producer=key[1], declared=True)
    return BeliefGraph(declarations=decls, beliefs=beliefs, edges=sorted(edges.values(), key=lambda e: (e.consumer, e.producer)))
