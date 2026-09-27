import { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import { LineChart } from "echarts/charts";
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  AriaComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import type { KPI } from "./types";
echarts.use([
  LineChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  AriaComponent,
  CanvasRenderer,
]);
export function Chart({ history }: { history: KPI[] }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current || !history.length) return;
    const chart = echarts.init(ref.current);
    chart.setOption({
      animation: false,
      aria: { enabled: true },
      textStyle: { fontFamily: "Inter, system-ui, sans-serif" },
      grid: { left: 50, right: 64, top: 25, bottom: 38 },
      tooltip: {
        trigger: "axis",
        backgroundColor: "#101a30",
        borderColor: "#344665",
        textStyle: { color: "#edf2ff" },
      },
      xAxis: {
        type: "category",
        data: history.map((p) => `Day ${p.day}`),
        axisLine: { lineStyle: { color: "#354164" } },
        axisLabel: { color: "#a6b4d2", fontSize: 12 },
        boundaryGap: false,
      },
      yAxis: [
        {
          type: "value",
          name: "Fill rate",
          min: 0,
          max: 100,
          nameTextStyle: { color: "#a6b4d2" },
          axisLabel: { formatter: "{value}%", color: "#a6b4d2" },
          splitLine: { lineStyle: { color: "#222e4a", type: "dashed" } },
        },
        {
          type: "value",
          name: "Modeled cost",
          nameTextStyle: { color: "#a6b4d2" },
          axisLabel: {
            formatter: (v: number) => `$${Math.round(v / 1000)}k`,
            color: "#a6b4d2",
          },
          splitLine: { show: false },
        },
      ],
      series: [
        {
          name: "Cumulative fill rate (%)",
          type: "line",
          data: history.map((p) =>
            p.service_level == null
              ? null
              : Math.round(p.service_level * 10000) / 100,
          ),
          smooth: false,
          symbol: "none",
          lineStyle: { color: "#67e8f9", width: 2.5 },
          itemStyle: { color: "#67e8f9" },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: "rgba(103,232,249,.22)" },
              { offset: 1, color: "rgba(103,232,249,0)" },
            ]),
          },
        },
        {
          name: "Cumulative modeled cost ($)",
          type: "line",
          yAxisIndex: 1,
          data: history.map((p) => p.total_cost),
          symbol: "none",
          lineStyle: { color: "#a78bfa", width: 2, type: "dashed" },
          itemStyle: { color: "#a78bfa" },
        },
      ],
    });
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(ref.current);
    return () => {
      observer.disconnect();
      chart.dispose();
    };
  }, [history]);
  return (
    <div className="chart-wrap">
      <div
        className="chart"
        ref={ref}
        role="img"
        aria-label="Daily cumulative fill rate and modeled cost"
      />
      {!history.length && (
        <div className="empty chart-empty">
          Advance the simulation to see measured performance.
        </div>
      )}
    </div>
  );
}
