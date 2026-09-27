# Measured benchmark results

Measured 2026-09-27T19:50:19.336592+00:00 on Darwin arm64, Python 3.12.14, 10 logical CPUs.

200 SKUs; 3 days; paired seeds [42]. Costs are modeled, not real operating savings.
No-LLM agents deliberately share the heuristic policy. LLM accuracy is null without independently labeled model decisions.

| Policy / runtime | Seed | Fill rate | Modeled cost | Lost units | Stockout lines | Working capital | Annual turns | Expedite | Mean plan ms | Run s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| reorder_point / none | 42 | 99.42% | $226,847.04 | 88 | 0.53% | $812,428 | 40.61 | 0.00% | 0.89 | 0.06 |
| min_max / none | 42 | 99.42% | $205,137.79 | 88 | 0.53% | $791,072 | 40.61 | 0.00% | 0.79 | 0.06 |
| heuristic / none | 42 | 99.42% | $305,166.29 | 88 | 0.53% | $889,399 | 40.61 | 2.92% | 1.01 | 0.06 |
| agents / none | 42 | 99.42% | $305,166.29 | 88 | 0.53% | $889,399 | 40.61 | 2.92% | 1.09 | 0.06 |
| agents / qwen3:8b | 42 | 99.42% | $305,177.79 | 88 | 0.53% | $889,722 | 40.61 | 0.00% | 11517.60 | 34.64 |

Timing excludes database and HTTP. See results.json for model failures, invalid actions, state hashes and configuration.
Tool-routing fixture accuracy is a software correctness measure; it is not evidence of local-model intelligence.
