import { useEffect, useState } from "react";
import { Cpu, FlaskConical, RefreshCw } from "lucide-react";
import { api } from "../api";
import type { Config, ModelCatalog, Page } from "../types";
import { Modal } from "./ui";
import { policyNames, defaultConfig } from "../config";

export function CreateModal({
  onClose,
  onCreate,
  busy,
  defaultDataset,
}: {
  onClose: () => void;
  onCreate: (c: Config, d: string) => void;
  busy: boolean;
  defaultDataset?: string;
}) {
  const [config, setConfig] = useState<Config>(defaultConfig),
    [datasets, setDatasets] = useState<{ id: string }[]>([]),
    [dataset, setDataset] = useState(
      defaultDataset || "synthetic-v1-seed-42-n-200",
    );
  const [catalog, setCatalog] = useState<ModelCatalog | null>(null);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    api<Page<{ id: string }>>("/datasets?limit=200")
      .then((r) => setDatasets(r.items))
      .catch(() => setDatasets([{ id: dataset }]));
  }, [dataset]);
  useEffect(() => {
    const runtime = config.runtime;
    if (runtime === "none") return;
    let active = true;
    api<ModelCatalog>(`/models?runtime=${runtime}`)
      .then((result) => {
        if (active) setCatalog(result);
      })
      .catch(() => {
        if (active)
          setCatalog({
            runtime,
            available: false,
            models: [],
            message:
              "Model discovery is unavailable. You can still enter your installed model ID.",
          });
      });
    return () => {
      active = false;
    };
  }, [config.runtime, revision]);
  return (
    <Modal title="Create an experiment" onClose={onClose}>
      <p className="help">
        Every episode starts from the same dataset. Use the same seed and
        horizon for paired policy comparisons.
      </p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          onCreate(config, dataset);
        }}
      >
        <label>
          Dataset
          <select
            aria-label="Dataset"
            value={dataset}
            onChange={(e) => setDataset(e.target.value)}
          >
            {datasets.map((d) => (
              <option key={d.id}>{d.id}</option>
            ))}
          </select>
        </label>
        <div className="form-grid">
          <label>
            Decision policy
            <select
              aria-label="Decision policy"
              value={config.policy}
              onChange={(e) =>
                setConfig({
                  ...config,
                  policy: e.target.value as Config["policy"],
                  runtime: "none",
                  model: "",
                })
              }
            >
              {Object.entries(policyNames).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </label>
          <label>
            Operating mode
            <select
              aria-label="Operating mode"
              value={config.mode}
              onChange={(e) =>
                setConfig({ ...config, mode: e.target.value as Config["mode"] })
              }
            >
              <option value="autonomous">Autonomous research</option>
              <option value="approval">Human approval</option>
            </select>
          </label>
          <label>
            Simulation days
            <input
              type="number"
              min="1"
              max="365"
              value={config.days}
              onChange={(e) => setConfig({ ...config, days: +e.target.value })}
            />
          </label>
          <label>
            Random seed
            <input
              type="number"
              min="0"
              max="2147483647"
              value={config.seed}
              onChange={(e) => setConfig({ ...config, seed: +e.target.value })}
            />
          </label>
        </div>
        <label>
          Local model runtime
          <select
            aria-label="Local model runtime"
            disabled={config.policy !== "agents"}
            value={config.runtime}
            onChange={(e) => {
              setCatalog(null);
              setConfig({
                ...config,
                runtime: e.target.value as Config["runtime"],
                model: "",
              });
            }}
          >
            <option value="none">
              No LLM · deterministic specialist tools
            </option>
            <option value="ollama">Ollama</option>
            <option value="llamacpp">llama.cpp</option>
            <option value="vllm">vLLM</option>
          </select>
        </label>
        {config.runtime !== "none" && (
          <div className="model-picker">
            <div className="model-picker-head">
              <span>
                <Cpu size={18} /> Bring your own model
              </span>
              <button
                type="button"
                className="text-button"
                onClick={() => {
                  setCatalog(null);
                  setRevision((r) => r + 1);
                }}
              >
                <RefreshCw size={14} /> Refresh models
              </button>
            </div>
            <p className="help">
              Use any compatible local model installed on your machine. Choose
              the model that fits your hardware and research.
            </p>
            <label>
              Available local models
              <select
                aria-label="Available local models"
                value={
                  catalog?.models.some((m) => m.id === config.model)
                    ? config.model
                    : ""
                }
                onChange={(e) =>
                  setConfig({ ...config, model: e.target.value })
                }
              >
                <option value="">
                  {catalog
                    ? "Select a model, or enter an ID below"
                    : "Checking your local runtime…"}
                </option>
                {catalog?.models.map((m) => (
                  <option value={m.id} key={m.id}>
                    {m.id}
                    {m.parameters ? ` · ${m.parameters}` : ""}
                    {m.quantization ? ` · ${m.quantization}` : ""}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Model ID
              <input
                required
                maxLength={150}
                placeholder="Exact installed tag or served model ID"
                value={config.model}
                onChange={(e) =>
                  setConfig({ ...config, model: e.target.value })
                }
              />
            </label>
            <p className="catalog-status" role="status">
              {catalog?.message ||
                "Discovering installed models without loading them…"}
            </p>
            <p className="help">
              Use a text/chat model with structured JSON support. The runtime
              must already have it installed. Compare quality with the same seed
              and horizon; failed inference is recorded and uses deterministic
              fallback.
            </p>
          </div>
        )}
        <button
          type="submit"
          className="primary full"
          disabled={busy || (config.runtime !== "none" && !config.model.trim())}
        >
          <FlaskConical size={16} />
          {busy ? "Creating…" : "Create episode"}
        </button>
      </form>
    </Modal>
  );
}
