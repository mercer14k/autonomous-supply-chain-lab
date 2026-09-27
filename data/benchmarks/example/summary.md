# Measured benchmark results

Measured 2026-09-27T20:07:53.111899+00:00 on Darwin arm64, Python 3.12.14, 10 logical CPUs.

200 SKUs; 30 days; paired seeds [42, 73, 101]. Costs are modeled, not real operating savings.
No-LLM agents deliberately share the heuristic policy. LLM accuracy is null without independently labeled model decisions.

| Policy / runtime | Seed | Fill rate | Modeled cost | Lost units | Stockout lines | Working capital | Annual turns | Expedite | Mean plan ms | Run s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| reorder_point / none | 42 | 92.37% | $2,430,289.35 | 10,876 | 7.53% | $910,380 | 59.53 | 0.00% | 0.95 | 0.81 |
| reorder_point / none | 73 | 92.47% | $2,403,543.01 | 10,680 | 7.51% | $899,855 | 59.10 | 0.00% | 1.22 | 0.83 |
| reorder_point / none | 101 | 92.87% | $2,385,096.16 | 10,134 | 7.21% | $890,410 | 58.98 | 0.00% | 0.96 | 0.82 |
| min_max / none | 42 | 86.42% | $2,648,932.97 | 19,360 | 12.80% | $1,007,622 | 44.03 | 0.00% | 1.18 | 0.74 |
| min_max / none | 73 | 87.49% | $2,605,492.75 | 17,741 | 12.14% | $992,363 | 44.54 | 0.00% | 1.11 | 0.81 |
| min_max / none | 101 | 87.20% | $2,653,237.35 | 18,183 | 12.31% | $1,031,279 | 43.82 | 0.00% | 1.01 | 0.78 |
| heuristic / none | 42 | 94.93% | $2,574,001.25 | 7,223 | 4.86% | $1,094,704 | 47.04 | 9.86% | 1.06 | 0.86 |
| heuristic / none | 73 | 95.18% | $2,528,788.84 | 6,837 | 4.74% | $1,067,294 | 47.14 | 8.46% | 1.33 | 0.86 |
| heuristic / none | 101 | 95.23% | $2,550,647.32 | 6,774 | 4.57% | $1,087,874 | 46.71 | 8.45% | 1.09 | 0.87 |
| agents / none | 42 | 94.93% | $2,574,001.25 | 7,223 | 4.86% | $1,094,704 | 47.04 | 9.86% | 1.48 | 0.89 |
| agents / none | 73 | 95.18% | $2,528,788.84 | 6,837 | 4.74% | $1,067,294 | 47.14 | 8.46% | 1.18 | 0.85 |
| agents / none | 101 | 95.23% | $2,550,647.32 | 6,774 | 4.57% | $1,087,874 | 46.71 | 8.45% | 1.19 | 0.85 |

Timing excludes database and HTTP. See results.json for model failures, invalid actions, state hashes and configuration.
Tool-routing fixture accuracy is a software correctness measure; it is not evidence of local-model intelligence.
