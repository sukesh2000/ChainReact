import pytest
from pydantic import ValidationError

from chainreact.contracts import *

EV = Evidence(repo="r", path="p")


def test_belief_requires_evidence():
    with pytest.raises(ValidationError):
        Belief(consumer="a", producer="b", endpoint="GET /x", field="f", evidence=[])


def test_learned_suppression_cannot_target_critical():
    with pytest.raises(ValidationError):
        LearnedRule(id="1", kind="suppression", pattern="severity=CRITICAL", author="a", source_pr="x")


def test_partial_failure_detected():
    g = FixGroup(disagreement_id="d", prs=[
        FixPR(disagreement_id="d", repo="a", branch="b", status=PRStatus.OPENED),
        FixPR(disagreement_id="d", repo="c", branch="b", status=PRStatus.FAILED)])
    assert g.partial_failure


def test_no_merge_in_fixpr():
    assert not any("merge" in f for f in FixPR.model_fields)
