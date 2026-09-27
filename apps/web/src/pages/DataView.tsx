import { useState } from "react";
import { Database, ArrowDownToLine } from "lucide-react";
import { getToken } from "../api";
import type { Network, ValidationReport } from "../types";
import { PanelTitle } from "../components/ui";

export function DataView({
  network,
  onError,
  onInspect,
}: {
  network: Network | null;
  onError: (x: string) => void;
  onInspect: (x: unknown) => void;
}) {
  const [report, setReport] = useState<ValidationReport | null>(null),
    [busy, setBusy] = useState(false);
  const upload = async (file: File) => {
    setBusy(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const response = await fetch("/api/v1/datasets/import", {
        method: "POST",
        headers: { Authorization: `Bearer ${getToken()}` },
        body: form,
      });
      const result = await response.json();
      if (result.error?.report) {
        setReport(result.error.report);
      } else if (result.error) {
        throw new Error(result.error.message);
      } else {
        setReport(result);
      }
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="data-grid">
      <section className="panel">
        <PanelTitle title="Dataset provenance" note="RAW INPUT" />
        <div className="data-body">
          <Database size={28} className="lime" />
          <h2>{network?.id}</h2>
          <p>
            Generated from a fixed seed with stable identifiers, explicit
            lineage, and known scenario ground truth.
          </p>
          <dl>
            <dt>Record count</dt>
            <dd>{network?.validation.record_count}</dd>
            <dt>Generator</dt>
            <dd>1.0 · fixed synthetic epoch</dd>
            <dt>Validation</dt>
            <dd>
              {network?.validation.accepted
                ? "Accepted with warnings"
                : "Unavailable"}
            </dd>
            <dt>Demand model</dt>
            <dd>Seeded stochastic daily lost sales</dd>
          </dl>
          <button
            className="secondary"
            onClick={() => onInspect(network?.validation)}
          >
            Inspect full report
          </button>
        </div>
      </section>
      <section className="panel">
        <PanelTitle title="Import & validate" note="JSON · MAX 10 MIB" />
        <div className="data-body">
          <label className="upload-zone">
            <ArrowDownToLine size={26} />
            <b>{busy ? "Validating dataset…" : "Select a dataset JSON file"}</b>
            <span>Invalid records are reported. Imports are atomic.</span>
            <input
              type="file"
              accept="application/json,.json"
              disabled={busy}
              onChange={(e) => {
                if (e.target.files?.[0]) upload(e.target.files[0]);
              }}
            />
          </label>
          {report && (
            <div
              className={`alert ${report.accepted ? "success" : "error"}`}
              role="status"
            >
              {report.accepted ? "Dataset accepted" : "Dataset rejected"} ·{" "}
              {report.errors.length} errors · {report.warnings.length} warnings
              <button className="text-button" onClick={() => onInspect(report)}>
                View report
              </button>
            </div>
          )}
          <p className="help">
            Accepted datasets become available in the New episode dialog.
            Existing dataset identifiers cannot be overwritten with different
            content.
          </p>
        </div>
      </section>
      <section className="panel span-two">
        <PanelTitle
          title="Seeded data quality findings"
          note="EXPLICIT EDGE CASES"
        />
        {network?.validation.warnings.map((w) => (
          <div className="finding" key={w.record_id}>
            <span className="pill warn">Warning</span>
            <b>{w.record_id}</b>
            <span>{w.message}</span>
          </div>
        ))}
      </section>
    </div>
  );
}
