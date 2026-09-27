# Contributing

Use Python 3.12+ and Node 22 with pnpm 11.25.0. Follow the [native quick start](docs/getting-started.md).

Before opening a pull request:

1. Run `ruff check src tests scripts apps/api`, `ruff format --check src tests scripts apps/api`, and `pytest -q`.
2. In `apps/web`, run `pnpm lint`, `pnpm typecheck`, `pnpm test`, and `pnpm build`.
3. With the app running, run `pnpm test:e2e` from `apps/web`.
4. Add meaningful regression tests for changed calculations or state transitions.
5. Re-run paired benchmarks when changing the simulation or decision policies; commit real metadata and results.
6. Document changed assumptions, licenses, schemas and replay compatibility. Never silently change engine semantics for existing saved episodes.

Keep domain rules out of API routes and UI components. No model-generated code or SQL execution, paid core dependencies, fabricated performance claims, or private datasets. New local-model integrations must fail safely and preserve no-LLM operation.

Use focused commits and PRs. Describe the behavioral change, validation evidence and remaining limitations. Security reports belong in the private reporting channel described in SECURITY.md, not a public issue.
