# studio

Knowledge Graph Studio subsystem: the browser-based authoring environment for
the knowledge graph, the business-rules registry, and the metrics registry.
Covered by Chapters 4 and 5 of the book.

**Not implemented at the `chapter-01` tag.** The Studio has its own stack
(separate `package.json`, its own frontend framework choice) and is covered by
a separate design document. This directory exists as a placeholder so the
monorepo layout matches Section 4 of the pipeline plan.

## Interaction with other subsystems

At the monorepo level, only two things matter:

- The Studio reads from and writes to the root `rules/` and `spec/` directories.
- Its outputs (updated rule YAML, updated metric YAML) are consumed by the
  dataset pipeline and the MCP Server on the next run.

The Studio does not need SQL literacy: it edits YAML, commits to git, and the
dataset pipeline's codegen step (Phase 8 of `docs/implementation_guide.md`)
turns it into dbt macros and models on build.
