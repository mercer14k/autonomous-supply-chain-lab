import type { Config } from "./types";
export const policyNames = {
  agents: "Specialist agents",
  heuristic: "Deterministic heuristic",
  min_max: "Min / max",
  reorder_point: "Reorder point",
};
export const defaultConfig: Config = {
  seed: 42,
  days: 30,
  policy: "agents",
  mode: "autonomous",
  runtime: "none",
  model: "",
};
