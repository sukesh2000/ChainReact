# ChainReact — Revised Plan (v2)

Supersedes the original plan. Changes are marked **[Δ]** with the review finding they resolve.

## Decisions
- **[Δ5,6] Belief source of truth = AST (tree-sitter) usage extraction.** RAG only enriches with semantic context (docs, annotations, unit hints). Detection never depends on retrieval for *completeness*.
- **[Δ] LlamaIndex scope:** used for ingesting/chunking *unstructured* content (docs, READMEs, `ARCHITECTURE.md`, code files via its tree-sitter CodeSplitter) and as the pgvector adapter. It stays behind our `Embedder`/`VectorStore` interfaces; detection code never imports it. Structured chunks (spec field declarations) are built by our own code.
- **[Δ] Runtime:** Python 3.11+ (3.12 via uv), PostgreSQL 16 + pgvector.
- **[Δ4] Durability:** LangGraph with the **Postgres checkpointer**; interrupts survive restarts. Out of scope: arbitrary mid-step infra failure (Temporal-class).
- **[Δ7] Service registry:** `ServiceEdge(consumer, producer, evidence)` from a declared `chainreact.yaml` registry, plus AST-inferred candidate edges needing confirmation.
- **[Δ8] Fix direction:** every `Disagreement` has `fix_side` (consumer | producer | ambiguous). Ambiguous => human interrupt.
- **[Δ9] Grouped fixes:** `FixGroup` tracks N consumer PRs with per-PR status; partial failure is reported and retryable, never silent.
- **[Δ12] LLM/embedding swappability:** three provider seams (analysis LLM, fix LLM, embeddings), each Claude/Ollama-swappable. Embedding model change => re-index (dimension recorded in schema). "No code leaves infra" holds only in local-model mode; docs say so.
- **[Δ10] No auto-merge, enforced:** GitHub App has no merge permission; branch protection requires review; a test asserts the client exposes no merge call.
- **[Δ11] Security:** webhook HMAC verification; `/learn` only from authorized maintainers; learned suppressions cannot suppress CRITICAL; rules carry author, source PR, expiry; repo content treated as untrusted in prompts.

## Time budget **[Δ3]**
Detect < 2 min from PR-open; fix PRs raised < 5 min from PR-open. Demo measured on both.

## Phases (reordered **[Δ1,2]**)
0. Contracts + fixture repos + eval set (decoys still to add before Phase 2) **[Δ13,14,15]**
1. Ingest (AST beliefs, registry, spec parser, embeddings, retrieval)
2. Detect — schema + semantic only (rename, unit mismatch). Rules engine first; LLM only for unresolved. Suppression rules derived from measured false positives, not a fixed count.
3. Architecture Review — owns circular-dependency / layering detection (moved earlier; Detect no longer claims it)
4. Auto-Fix — after 3, so the interrupt path is tested against real `ArchitectureViolation`s
5. Learn
6. Platform (integrates per phase)
7. QA: demo + eval set (precision/recall targets, decoys)
8. Docs (incrementally per phase; final pass here)

## Build agents
Collapse to: Planner (me), Ingest, Detect+Review, Fix+Learn, Platform, QA. Docs written alongside each phase.

## Definition of done
All phase exit criteria; demo within budget; eval precision/recall met; no `ANTHROPIC_API_KEY` needed outside the provider seams.
