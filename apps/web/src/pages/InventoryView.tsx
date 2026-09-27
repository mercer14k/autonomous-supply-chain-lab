import { useEffect, useState } from "react";
import { Search, ChevronLeft, ChevronRight, ArrowRight } from "lucide-react";
import { api, number } from "../api";
import type { Episode, Page, Inventory } from "../types";

export function InventoryView({
  episode,
  warehouses,
  onInspect,
  onError,
}: {
  episode: Episode;
  warehouses: { id: string; name: string }[];
  onInspect: (x: unknown) => void;
  onError: (x: string) => void;
}) {
  const [q, setQ] = useState(""),
    [warehouse, setWarehouse] = useState(""),
    [risk, setRisk] = useState(false),
    [offset, setOffset] = useState(0),
    [rows, setRows] = useState<Page<Inventory> | null>(null),
    [loading, setLoading] = useState(false);
  useEffect(() => {
    let active = true;
    setLoading(true);
    const timer = setTimeout(() => {
      api<Page<Inventory>>(
        `/episodes/${episode.id}/inventory?q=${encodeURIComponent(q)}&warehouse=${encodeURIComponent(warehouse)}&at_risk=${risk}&offset=${offset}`,
      )
        .then((r) => {
          if (active) setRows(r);
        })
        .catch((e) => {
          if (active) onError(e.message);
        })
        .finally(() => {
          if (active) setLoading(false);
        });
    }, 180);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [episode.id, episode.day, q, warehouse, risk, offset, onError]);
  return (
    <section className="panel">
      <div className="table-toolbar">
        <div className="search">
          <Search size={17} />
          <input
            aria-label="Search inventory"
            placeholder="Search SKU or product…"
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setOffset(0);
            }}
          />
        </div>
        <select
          aria-label="Warehouse"
          value={warehouse}
          onChange={(e) => {
            setWarehouse(e.target.value);
            setOffset(0);
          }}
        >
          <option value="">All warehouses</option>
          {warehouses.map((w) => (
            <option key={w.id} value={w.id}>
              {w.name}
            </option>
          ))}
        </select>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={risk}
            onChange={(e) => {
              setRisk(e.target.checked);
              setOffset(0);
            }}
          />
          At risk only
        </label>
        <span className="source-label">COMPUTED OBSERVATIONS</span>
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              {[
                "Product / SKU",
                "Warehouse",
                "On hand",
                "Inbound",
                "Daily forecast",
                "Days cover",
                "Status",
                "Evidence",
              ].map((x) => (
                <th key={x}>{x}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows?.items.map((r) => (
              <tr key={r.id}>
                <td>
                  <b>{r.name}</b>
                  <small>
                    {r.sku_id} · {r.category}
                  </small>
                </td>
                <td>{r.warehouse_id}</td>
                <td>{number(r.on_hand)}</td>
                <td>{number(r.pipeline)}</td>
                <td>{r.daily_forecast?.toFixed(1) ?? "Unavailable"}</td>
                <td>{r.days_cover?.toFixed(1) ?? "—"}</td>
                <td>
                  <span
                    className={`pill ${r.daily_forecast && r.days_cover! < r.lead_days ? "warn" : "neutral"}`}
                  >
                    {r.daily_forecast == null
                      ? "Missing evidence"
                      : r.daily_forecast === 0
                        ? "No demand"
                        : r.days_cover! < r.lead_days
                          ? "At risk"
                          : "Covered"}
                  </span>
                </td>
                <td>
                  <button className="text-button" onClick={() => onInspect(r)}>
                    Inspect <ArrowRight size={14} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!loading && rows?.items.length === 0 && (
          <div className="empty">No inventory matches your filters.</div>
        )}
      </div>
      <div className="pagination">
        <span aria-live="polite">
          {loading
            ? "Loading…"
            : `${number(rows?.total)} inventory lines · ${offset + 1}–${offset + (rows?.items.length || 0)}`}
        </span>
        <div className="button-row">
          <button
            className="secondary small"
            disabled={offset === 0 || loading}
            onClick={() => setOffset(Math.max(0, offset - 30))}
          >
            <ChevronLeft size={16} />
            Previous
          </button>
          <button
            className="secondary small"
            disabled={!rows || offset + 30 >= rows.total || loading}
            onClick={() => setOffset(offset + 30)}
          >
            Next
            <ChevronRight size={16} />
          </button>
        </div>
      </div>
    </section>
  );
}
