# evaluation

The evaluation harness sits at the monorepo root as a peer to the three
subsystems (`dataset/`, `mcp_server/`, `studio/`), not inside any one of them.
It depends on all three and putting it anywhere else would distort the
dependency direction. Chapter 11 formalizes this harness as the book's main
release-gate argument.

**Not implemented at the `chapter-01` tag.** Phase 12 of
`docs/implementation_guide.md` populates each subdirectory.

## Layout

```
retrieval_tests/       # embedding recall, reranker accuracy (Chapter 6 material)
resolver_tests/        # Date, Recency, Grain resolver unit tests (Chapters 7-9)
sql_validation/        # generated SQL executed against BigQuery
golden_answers/
  kpi_snapshots.csv    # pinned expected KPI values from the canonical run
regression_harness/    # compares live kpi_snapshots to the committed golden answers
```

## Guarantees

The harness exercises all three subsystems together. At dev scale it runs in
under five minutes and is the CI gate on every commit. At canonical scale it
produces the pinned `golden_answers/kpi_snapshots.csv` that the book's
numerical claims reference. Any deviation beyond 1% between a live run and the
pinned answers fails the pipeline — see pipeline plan Section 7.4 for the
tolerance justification.
