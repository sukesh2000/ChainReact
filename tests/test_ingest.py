from pathlib import Path

from chainreact.ingest.graph import build_graph

REG = Path(__file__).parent.parent / "fixtures" / "chainreact.yaml"
G = build_graph(REG)


def test_declarations():
    names = {(d.service, d.name) for d in G.declarations}
    assert ("user-service", "fullName") in names
    total = next(d for d in G.declarations if d.name == "total")
    assert total.unit == "paise"


def test_edges_include_circular_pair():
    pairs = {(e.consumer, e.producer): e.declared for e in G.edges}
    assert ("user-service", "order-service") in pairs and ("order-service", "user-service") in pairs
    assert pairs[("order-service", "user-service")] is True
    assert pairs[("quickbite", "order-service")] is False


def test_beliefs_cover_all_consumers():
    got = {(b.consumer, b.producer, b.field) for b in G.beliefs}
    assert {("order-service", "user-service", "name"), ("recommendation-service", "user-service", "name"),
            ("quickbite", "user-service", "name"), ("recommendation-service", "order-service", "total"),
            ("quickbite", "order-service", "total")} <= got


def test_unit_hints():
    units = {(b.consumer, b.field): b.assumed_unit for b in G.beliefs if b.field == "total"}
    assert units[("recommendation-service", "total")] == "rupee"
    assert units[("quickbite", "total")] == "rupee"


def test_retrieval_and_incremental_embedding():
    from chainreact.ingest.retrieval import HashEmbedder, VectorStore, chunks_from_decls
    store = VectorStore(HashEmbedder())
    ch = chunks_from_decls(G.declarations)
    assert store.upsert(ch) == len(ch)
    assert store.upsert(ch) == 0  # unchanged => no re-embedding
    top = store.query("order total unit paise", k=1)[0]
    assert top.service == "order-service" and "total" in top.key
    assert store.query("fullName", k=3, service="user-service")[0].key.endswith("fullName")
