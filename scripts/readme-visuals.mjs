// Rebuild the measured README chart after changing committed benchmark results.
// Uses the existing frontend ECharts dependency; no new plotting dependency.
import { createRequire } from "node:module";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { resolve, dirname } from "node:path";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const require = createRequire(resolve(root, "apps/web/package.json"));
const echarts = require("echarts");
const report = JSON.parse(
  readFileSync(resolve(root, "data/benchmarks/example/results.json"), "utf8"),
);
const matrix = report.methodology;
const environment = report.metadata;
const measuredDate = new Date(environment.measured_at).toLocaleDateString(
  "en-GB",
  {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  },
);
const platform = environment.os === "Darwin" ? "macOS" : environment.os;
const policies = ["reorder_point", "min_max", "heuristic", "agents"];
const names = ["Reorder point", "Min / max", "Heuristic", "Agents · no LLM"];
const colors = ["#77aafb", "#8a9bb7", "#5bd9e5", "#ad9af6"];
const mean = (items, field) =>
  items.reduce((sum, row) => sum + row[field], 0) / items.length;
const values = policies.map((policy) => {
  const rows = report.results.filter(
    (row) => row.policy === policy && row.runtime === "none",
  );
  if (
    !rows.length ||
    rows.length !== matrix.seeds.length ||
    new Set(rows.map((row) => row.seed)).size !== matrix.seeds.length ||
    !rows.every(
      (row) =>
        matrix.seeds.includes(row.seed) &&
        row.days === matrix.days &&
        row.sku_count === matrix.sku_count,
    )
  ) {
    throw new Error(
      "Update the chart methodology labels for this benchmark matrix.",
    );
  }
  return {
    fill: 100 * mean(rows, "service_level"),
    cost: mean(rows, "total_cost"),
  };
});
const chart = echarts.init(null, null, {
  renderer: "svg",
  ssr: true,
  width: 1200,
  height: 484,
});
chart.setOption({
  animation: false,
  backgroundColor: "#0b1526",
  textStyle: { fontFamily: "Arial, Helvetica, sans-serif", color: "#d6e1f2" },
  title: [
    {
      text: "SERVICE HAS A COST",
      left: 36,
      top: 26,
      textStyle: { fontSize: 24, color: "#f0f5ff", fontWeight: 700 },
    },
    {
      text: `Measured policy trade-offs · ${matrix.sku_count} SKUs · ${matrix.days} days · ${matrix.seeds.length} paired seeds`,
      left: 36,
      top: 66,
      textStyle: { fontSize: 16, color: "#a6b9d1", fontWeight: 400 },
    },
    {
      text: "DEMAND FILL RATE",
      left: 216,
      top: 119,
      textStyle: { fontSize: 13, color: "#b9cbe1", fontWeight: 600 },
    },
    {
      text: "TOTAL MODELED COST",
      left: 708,
      top: 119,
      textStyle: { fontSize: 13, color: "#b9cbe1", fontWeight: 600 },
    },
  ],
  grid: [
    { left: 216, top: 159, width: 370, height: 213 },
    { left: 708, top: 159, width: 356, height: 213 },
  ],
  xAxis: [
    {
      type: "value",
      gridIndex: 0,
      min: 0,
      max: 100,
      interval: 20,
      axisLabel: { color: "#a5b5ce", formatter: "{value}%", fontSize: 12 },
      splitLine: { lineStyle: { color: "#233046" } },
    },
    {
      type: "value",
      gridIndex: 1,
      min: 0,
      max:
        Math.ceil((Math.max(...values.map((v) => v.cost)) * 1.1) / 1000000) *
        1000000,
      interval: 1000000,
      axisLabel: {
        color: "#a5b5ce",
        formatter: (v) => `$${v / 1000000}m`,
        fontSize: 12,
      },
      splitLine: { lineStyle: { color: "#233046" } },
    },
  ],
  yAxis: [
    {
      type: "category",
      gridIndex: 0,
      data: names,
      inverse: true,
      axisLabel: { color: "#e2eaf7", fontSize: 17, margin: 20 },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    {
      type: "category",
      gridIndex: 1,
      data: names,
      inverse: true,
      axisLabel: { show: false },
      axisLine: { show: false },
      axisTick: { show: false },
    },
  ],
  series: [
    {
      type: "bar",
      xAxisIndex: 0,
      yAxisIndex: 0,
      barWidth: 20,
      itemStyle: { borderRadius: [0, 4, 4, 0] },
      label: {
        show: true,
        position: "right",
        distance: 12,
        color: "#f0f5ff",
        fontSize: 16,
        formatter: (p) => `${p.value.toFixed(2)}%`,
      },
      data: values.map((v, i) => ({
        value: v.fill,
        itemStyle: { color: colors[i] },
      })),
    },
    {
      type: "bar",
      xAxisIndex: 1,
      yAxisIndex: 1,
      barWidth: 20,
      itemStyle: { borderRadius: [0, 4, 4, 0] },
      label: {
        show: true,
        position: "right",
        distance: 12,
        color: "#f0f5ff",
        fontSize: 16,
        formatter: (p) => `$${Math.round(p.value).toLocaleString("en-US")}`,
      },
      data: values.map((v, i) => ({
        value: v.cost,
        itemStyle: { color: colors[i] },
      })),
    },
  ],
  graphic: [
    {
      type: "text",
      left: 36,
      top: 416,
      style: {
        text: "No-LLM agents intentionally match the heuristic. Costs include purchases; ending stock receives no credit.",
        font: "14px Arial",
        fill: "#bdcce1",
      },
    },
    {
      type: "text",
      left: 36,
      top: 444,
      style: {
        text: `Measured ${measuredDate} · ${platform} ${environment.architecture} · Python ${environment.python} · Source: data/benchmarks/example/results.json`,
        font: "12px Arial",
        fill: "#a5b5ce",
      },
    },
  ],
});
const svg = chart
  .renderToSVGString()
  .replace(
    "<svg ",
    '<svg role="img" aria-label="Measured demand fill rates and total modeled costs; accessible values are in the README table" ',
  );
writeFileSync(resolve(root, "docs/assets/benchmark.svg"), svg + "\n");
chart.dispose();
console.log(
  "Updated docs/assets/benchmark.svg from committed benchmark results.",
);

const hero = readFileSync(resolve(root, "docs/assets/hero.svg"), "utf8");
const social = hero
  .replace(
    'height="420" viewBox="0 0 1280 420"',
    'height="640" viewBox="0 0 1280 640"',
  )
  .replace(
    '<rect width="1280" height="420"',
    '<rect width="1280" height="640" fill="#071321"/><rect width="1280" height="420"',
  )
  .replace(
    "</svg>",
    `<g font-family="Arial, Helvetica, sans-serif" text-anchor="middle">
    <text x="640" y="494" font-size="34" font-weight="700" fill="#edf5ff">LOCAL AI. MEASURABLE DECISIONS.</text>
    <text x="640" y="540" font-size="20" fill="#b2c7df">Compare service, cost and tool choices against deterministic baselines.</text>
    <text x="640" y="592" font-size="16" fill="#73e0e9">github.com/mercer14k/autonomous-supply-chain-lab</text>
  </g></svg>`,
  );
writeFileSync(resolve(root, "docs/assets/social-preview.svg"), social);

// Optional browser rendering for GitHub's PNG social-image format.
// Requires the existing Playwright dev dependency and its Chromium browser.
if (process.argv.includes("--render")) {
  const { chromium } = require("@playwright/test");
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE }
      : {}),
  });
  try {
    const page = await browser.newPage({
      viewport: { width: 1280, height: 640 },
      deviceScaleFactor: 1,
    });
    await page.setContent(
      `<html><body style="margin:0">${social}</body></html>`,
    );
    await page.screenshot({
      path: resolve(root, "docs/assets/social-preview.png"),
    });
    console.log("Rendered docs/assets/social-preview.png (1280 × 640).");
  } finally {
    await browser.close();
  }
}
