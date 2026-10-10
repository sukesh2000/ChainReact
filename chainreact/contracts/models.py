"""Frozen inter-stage contracts (Phase 0). Agents build against these, not each other's internals."""
from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = [
    "Severity", "FixSide", "PRStatus", "Evidence", "FieldDecl", "Belief", "ServiceEdge",
    "BeliefGraph", "Disagreement", "FixPR", "FixGroup", "ArchitectureViolation", "LearnedRule",
]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class FixSide(str, Enum):
    CONSUMER = "consumer"
    PRODUCER = "producer"
    AMBIGUOUS = "ambiguous"  # routed to human interrupt


class PRStatus(str, Enum):
    PENDING = "pending"
    OPENED = "opened"
    FAILED = "failed"


class Evidence(_Frozen):
    """Provenance for any claim: where it came from and how sure we are."""
    repo: str
    path: str
    line: Optional[int] = None
    snippet: str = ""
    source: str = "ast"  # ast | spec | rag | llm
    confidence: float = Field(1.0, ge=0.0, le=1.0)


class FieldDecl(_Frozen):
    """Producer-side declaration from an OpenAPI spec."""
    service: str
    endpoint: str          # e.g. "GET /users/{id}"
    name: str              # dotted path, e.g. "user.name"
    type: str
    format: Optional[str] = None
    nullable: bool = False
    enum: Optional[List[str]] = None
    unit: Optional[str] = None  # e.g. "paise"


class Belief(_Frozen):
    """Consumer-side assumption about a producer field."""
    consumer: str
    producer: str
    endpoint: str
    field: str
    assumed_type: Optional[str] = None
    assumed_unit: Optional[str] = None
    evidence: List[Evidence] = Field(min_length=1)


class ServiceEdge(_Frozen):
    consumer: str
    producer: str
    declared: bool  # False => AST-inferred, needs confirmation
    evidence: List[Evidence] = Field(default_factory=list)


class BeliefGraph(_Frozen):
    declarations: List[FieldDecl] = Field(default_factory=list)
    beliefs: List[Belief] = Field(default_factory=list)
    edges: List[ServiceEdge] = Field(default_factory=list)


class Disagreement(_Frozen):
    id: str
    producer: str
    consumers: List[str] = Field(min_length=1)
    field: str
    kind: str  # rename | type | enum | unit | nullability | behavioral
    severity: Severity
    fix_side: FixSide
    detected_by: str  # rules | llm
    explanation: str
    evidence: List[Evidence] = Field(min_length=1)


class FixPR(_Frozen):
    disagreement_id: str
    repo: str
    branch: str
    url: Optional[str] = None
    status: PRStatus = PRStatus.PENDING
    error: Optional[str] = None
    # Nothing auto-merges: there is deliberately no merge field/operation.


class FixGroup(_Frozen):
    disagreement_id: str
    prs: List[FixPR]

    @property
    def partial_failure(self) -> bool:
        s = {p.status for p in self.prs}
        return PRStatus.FAILED in s and PRStatus.OPENED in s


class ArchitectureViolation(_Frozen):
    id: str
    repo: str
    kind: str  # circular_dependency | layering | leaf_upstream_call | learned_rule
    description: str
    cycle: Optional[List[str]] = None
    severity: Severity = Severity.HIGH
    evidence: List[Evidence] = Field(min_length=1)
    requires_human: bool = True  # never auto-fixed


class LearnedRule(_Frozen):
    id: str
    kind: str  # architecture | suppression
    pattern: str
    author: str
    source_pr: str
    expires_at: Optional[str] = None  # ISO date

    @model_validator(mode="after")
    def _no_critical_suppression(self):
        if self.kind == "suppression" and "CRITICAL" in self.pattern.upper():
            raise ValueError("learned suppressions may not target CRITICAL severity")
        return self
