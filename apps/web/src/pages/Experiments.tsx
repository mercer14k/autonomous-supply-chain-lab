import { useEffect, useState } from "react";
import { ShieldCheck, ArrowDownToLine } from "lucide-react";
import { api, money, number, percent } from "../api";
import type { Episode, Page } from "../types";
import { PanelTitle } from "../components/ui";
import { policyNames } from "../config";

export function Experiments({
  current,
  onSelect,
  onReplay,
  onExport,
  onError,
}: {
  current: Episode | null;
  onSelect: (id: string) => void;
  onReplay: (id: string) => void;
  onExport: (id: string) => void;
  onError: (x: string) => void;
}) {
  const [episodes, setEpisodes] = useState<Episode[] | null>(null);
  useEffect(() => {
    let active = true;
    api<Page<{ id: string }>>("/episodes?limit=30")
      .then((r) =>
        Promise.all(r.items.map((e) => api<Episode>(`/episodes/${e.id}`))),
      )
      .then((r) => {
        if (active) setEpisodes(r);
      })
      .catch((e) => {
        if (active) onError(e.message);
      });
    return () => {
      active = false;
    };
  }, [current?.id, current?.day, onError]);
  return (
    <section className="panel">
      <PanelTitle title="Episode registry" note="MEASURED RESULTS" />
      <p className="section-help">
        Compare runs with matching dataset, seed, and horizon. Partial runs are
        labeled by elapsed days. No local-model performance is claimed without a
        real model run.
      </p>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              {[
                "Episode / policy",
                "Seed",
                "Horizon",
                "Fill rate",
                "Modeled cost",
                "Lost units",
                "Replay",
                "Export",
              ].map((x) => (
                <th key={x}>{x}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {episodes?.map((e) => (
              <tr key={e.id}>
                <td>
                  <button
                    className="text-button"
                    onClick={() => onSelect(e.id)}
                  >
                    {policyNames[e.config.policy]}
                  </button>
                  <small>
                    {e.id.slice(0, 8)} ·{" "}
                    {e.config.runtime === "none" ? "no LLM" : e.config.model}
                  </small>
                </td>
                <td>{e.config.seed}</td>
                <td>
                  {e.day} / {e.config.days} days
                </td>
                <td>{percent(e.kpis.service_level)}</td>
                <td>{money(e.kpis.total_cost)}</td>
                <td>{number(e.kpis.lost_units)}</td>
                <td>
                  <button
                    className="text-button"
                    onClick={() => onReplay(e.id)}
                  >
                    <ShieldCheck size={15} />
                    Verify
                  </button>
                </td>
                <td>
                  <button
                    className="icon-button"
                    aria-label={`Export episode ${e.id}`}
                    onClick={() => onExport(e.id)}
                  >
                    <ArrowDownToLine size={17} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {episodes?.length === 0 && (
          <div className="empty">
            Create an episode to begin comparing policies.
          </div>
        )}
        {!episodes && <div className="empty">Loading saved experiments…</div>}
      </div>
    </section>
  );
}
