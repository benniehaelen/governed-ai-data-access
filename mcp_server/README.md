# mcp_server

MCP Server subsystem: the nine-step query pipeline, the governed resolvers, the
knowledge graph client, the semantic index, authentication, observability, and
the business-rule resolver. Covered by Chapters 6 through 10 of the book.

**Not implemented at the `chapter-01` tag.** The directory tree below is the
target shape from the pipeline plan Section 4.3. Individual design decisions
(nine-step pipeline internals, dual-token auth pattern, observability schema)
live in a separate MCP Server design document.

## Layout

```
pyproject.toml                  # deferred until the MCP Server phase begins
config/
  app.yaml                      # tool registry, model names, timeouts
  environments/
src/mcp_server/
  app.py                        # MCP protocol entry, tool handlers
  pipeline/                     # nine-step query pipeline
    build_query.py              # top-level orchestrator
    semantic_search.py          # step 1
    authority_reranker.py       # step 2
    zone_router.py              # step 3
    prompt_assembler.py         # step 7
    gemini_client.py            # step 8
    bigquery_executor.py        # step 9
  resolvers/                    # steps 4-6
    date_resolver.py
    recency_resolver.py
    grain_resolver.py
  knowledge_graph/              # Neo4j schema, loader, Cypher
  semantic_index/               # Vertex AI embeddings, BigQuery load
  auth/                         # dual-token (Bearer JWT + GCP SA)
  observability/                # @trace_tool, mcp_request_log writer
  business_rules/               # reads ../../rules/business_rules/
tests/
  unit/                         # resolver and pipeline step tests
  integration/                  # end-to-end, NL question -> BigQuery row
```

`business_rules/` inside the MCP Server reads directly from the root
`rules/business_rules/` YAML at runtime. It does not import from the dataset
pipeline. Rules are owned by neither subsystem; both consume the same files.
