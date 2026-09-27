# Measured benchmark results

Measured 2026-09-27T20:14:24.969556+00:00 on Darwin arm64, Python 3.12.14, 10 logical CPUs.

200 SKUs; 30 days; paired seeds [42]. Costs are modeled, not real operating savings.
No-LLM agents deliberately share the heuristic policy. LLM accuracy is null without independently labeled model decisions.

| Policy / runtime | Seed | Fill rate | Modeled cost | Lost units | Stockout lines | Working capital | Annual turns | Expedite | Mean plan ms | Run s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| reorder_point / none | 42 | 92.37% | $2,430,289.35 | 10,876 | 7.53% | $910,380 | 59.53 | 0.00% | 1.03 | 0.86 |
| min_max / none | 42 | 86.42% | $2,648,932.97 | 19,360 | 12.80% | $1,007,622 | 44.03 | 0.00% | 1.03 | 0.79 |
| heuristic / none | 42 | 94.93% | $2,574,001.25 | 7,223 | 4.86% | $1,094,704 | 47.04 | 9.86% | 1.09 | 0.87 |
| agents / none | 42 | 94.93% | $2,574,001.25 | 7,223 | 4.86% | $1,094,704 | 47.04 | 9.86% | 1.44 | 0.87 |
| agents / qwen3:8b | 42 | 94.50% | $2,564,904.76 | 7,844 | 5.43% | $1,074,401 | 48.18 | 5.82% | 13144.26 | 395.44 |

Timing excludes database and HTTP. See results.json for model failures, invalid actions, state hashes and configuration.
Tool-routing fixture accuracy is a software correctness measure; it is not evidence of local-model intelligence.
