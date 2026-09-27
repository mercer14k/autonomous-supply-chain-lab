import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import {
  Activity,
  ArrowDownToLine,
  ArrowRight,
  Box,
  Check,
  ChevronRight,
  CircleHelp,
  Clock3,
  Database,
  FlaskConical,
  GitBranch,
  Layers3,
  LayoutDashboard,
  Menu,
  Pause,
  Play,
  Plus,
  ShieldCheck,
  SlidersHorizontal,
  Truck,
} from "lucide-react";
import { api, download, getToken, money, number, percent } from "./api";
import { Chart } from "./Chart";
import type { Config, Episode, Frame, Network, Page } from "./types";
import { Modal, PanelTitle, Metric, DecisionCard } from "./components/ui";
import { CreateModal } from "./components/CreateModal";
import { policyNames } from "./config";
import { InventoryView } from "./pages/InventoryView";
import { Experiments } from "./pages/Experiments";
import { DataView } from "./pages/DataView";
import { Architecture } from "./pages/Architecture";
import "./styles.css";

const NetworkScene = lazy(() => import("./components/NetworkScene"));

const pages = [
  { name: "Operations", icon: LayoutDashboard },
  { name: "Inventory", icon: Layers3 },
  { name: "Agent ledger", icon: Activity },
  { name: "Experiments", icon: FlaskConical },
  { name: "Data & provenance", icon: Database },
  { name: "Architecture", icon: GitBranch },
];

export default function App() {
  const [page, setPage] = useState("Operations");
  const [episode, setEpisode] = useState<Episode | null>(null);
  const [network, setNetwork] = useState<Network | null>(null);
  const [frames, setFrames] = useState<Frame[]>([]);
  const [busy, setBusy] = useState(false),
    [running, setRunning] = useState(false),
    [loading, setLoading] = useState(true);
  const [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [showCreate, setShowCreate] = useState(false),
    [showSettings, setShowSettings] = useState(false),
    [mobileNav, setMobileNav] = useState(false);
  const [detail, setDetail] = useState<{
    title: string;
    value: unknown;
  } | null>(null);
  const stop = useRef(false);
  const refreshFrames = useCallback(async (id: string) => {
    const response = await api<Page<Frame>>(`/episodes/${id}/frames?limit=200`);
    setFrames(response.items);
  }, []);
  const selectEpisode = useCallback(
    async (id: string) => {
      const ep = await api<Episode>(`/episodes/${id}`);
      setEpisode(ep);
      await refreshFrames(id);
      setNetwork(
        await api<Network>(
          `/network?dataset_id=${encodeURIComponent(ep.dataset_id)}`,
        ),
      );
    },
    [refreshFrames],
  );
  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [net, list] = await Promise.all([
          api<Network>("/network"),
          api<Page<{ id: string }>>("/episodes?limit=1"),
        ]);
        if (!active) return;
        setNetwork(net);
        if (list.items[0]) await selectEpisode(list.items[0].id);
      } catch (e) {
        if (active) setError((e as Error).message);
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
      stop.current = true;
    };
  }, [selectEpisode]);
  const work = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await fn();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const step = () =>
    episode &&
    work(async () => {
      const next = await api<Episode>(`/episodes/${episode.id}/step`, {
        method: "POST",
      });
      setEpisode(next);
      await refreshFrames(next.id);
    });
  const run = async () => {
    if (!episode) return;
    stop.current = false;
    setRunning(true);
    setBusy(true);
    setError("");
    let current = episode;
    try {
      while (!stop.current && current.status === "ready") {
        current = await api<Episode>(`/episodes/${current.id}/step`, {
          method: "POST",
        });
        setEpisode(current);
        await refreshFrames(current.id);
        await new Promise((r) => setTimeout(r, 180));
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setRunning(false);
      setBusy(false);
    }
  };
  const approve = (approve: boolean) =>
    episode &&
    work(async () => {
      const result = await api<Episode>(`/episodes/${episode.id}/approval`, {
        method: "POST",
        body: JSON.stringify({ approve }),
      });
      setEpisode(result);
      await refreshFrames(result.id);
    });
  const latest = frames.at(-1),
    k = episode?.kpis;
  const newEpisode = async (config: Config, dataset_id: string) => {
    await work(async () => {
      const ep = await api<Episode>("/episodes", {
        method: "POST",
        body: JSON.stringify({ config, dataset_id }),
      });
      setEpisode(ep);
      setFrames([]);
      setNetwork(
        await api<Network>(
          `/network?dataset_id=${encodeURIComponent(ep.dataset_id)}`,
        ),
      );
      setShowCreate(false);
      setPage("Operations");
    });
  };
  const inspect = async (day: number) => {
    await work(async () => {
      const value = await api(`/episodes/${episode?.id}/frames/${day}`);
      setDetail({ title: `Day ${day + 1} · evidence & balance ledger`, value });
    });
  };
  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileNav ? "open" : ""}`}>
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            setPage("Operations");
          }}
        >
          <span className="brand-mark">
            <Box size={23} />
          </span>
          <span>
            SUPPLY CHAIN<span className="brand-lab">AUTONOMOUS LAB</span>
          </span>
        </a>
        <div className="workspace-label">
          RESEARCH WORKSPACE <span>01</span>
        </div>
        <nav aria-label="Main navigation">
          {pages.map(({ name, icon: Icon }) => (
            <button
              key={name}
              className={page === name ? "nav-link active" : "nav-link"}
              onClick={() => {
                setPage(name);
                setMobileNav(false);
              }}
            >
              <Icon size={18} />
              {name}
              {name === "Agent ledger" && (
                <span className="nav-count">
                  {latest?.decisions.length || 0}
                </span>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-foot">
          <div className="local-runtime">
            <span className="status-dot" />
            <span>
              {episode?.config.runtime === "none" || !episode
                ? "LOCAL · DETERMINISTIC"
                : `LOCAL · ${episode.config.runtime.toUpperCase()}`}
            </span>
          </div>
          <p>
            Reproducible by design.
            <br />
            Every decision leaves evidence.
          </p>
          <button className="nav-link" onClick={() => setShowSettings(true)}>
            <SlidersHorizontal size={17} />
            Lab settings
          </button>
          <div className="version">
            ENGINE v{episode?.engine_version || "1.0"}{" "}
            <span>OPEN SOURCE ↗</span>
          </div>
        </div>
      </aside>
      <main>
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="icon-button mobile-menu"
              aria-label="Toggle navigation"
              onClick={() => setMobileNav(!mobileNav)}
            >
              <Menu size={20} />
            </button>
            <span>Workspace</span>
            <ChevronRight size={14} />
            <strong>{page}</strong>
          </div>
          <div className="topbar-right">
            <span className="research-label">
              <FlaskConical size={14} />
              Simulation environment
            </span>
            <button
              className="icon-button"
              aria-label="About this lab"
              onClick={() => setPage("Architecture")}
            >
              <CircleHelp size={19} />
            </button>
            <span className="avatar">SC</span>
          </div>
        </header>
        <div className="content">
          <div className="page-heading">
            <div>
              <div className="eyebrow">AUTONOMOUS SUPPLY CHAIN LAB</div>
              <h1>
                {page === "Operations" ? "Operations control room" : page}
              </h1>
              <p>
                {page === "Operations"
                  ? "Observe the network. Evaluate decisions. Measure the trade-offs."
                  : page === "Inventory"
                    ? "Inspect stock, inbound supply, and forecast evidence across your network."
                    : page === "Agent ledger"
                      ? "Observable tool calls and supporting evidence for every simulated day."
                      : page === "Experiments"
                        ? "Compare persisted runs using their measured operational outcomes."
                        : page === "Data & provenance"
                          ? "Trace synthetic inputs and inspect every validation finding."
                          : "A deterministic operating system for supply-chain research."}
              </p>
            </div>
            <button
              className="primary"
              onClick={() => setShowCreate(true)}
              disabled={busy}
            >
              <Plus size={17} />
              New episode
            </button>
          </div>
          {error && (
            <div className="alert error" role="alert">
              {error}
              <button className="text-button" onClick={() => setError("")}>
                Dismiss
              </button>
            </div>
          )}
          {notice && (
            <div className="alert success" role="status">
              {notice}
              <button className="text-button" onClick={() => setNotice("")}>
                Dismiss
              </button>
            </div>
          )}
          {loading ? (
            <div className="loading-panel">
              <Activity className="pulse" />
              Loading the lab and its persisted episodes…
            </div>
          ) : (
            <>
              {episode && (
                <div className="episode-bar">
                  <div className="episode-id">
                    <span
                      className={`status-dot ${episode.status === "completed" ? "blue" : ""}`}
                    />
                    <b>EP {episode.id.slice(0, 8).toUpperCase()}</b>
                    <span className="tag">
                      {policyNames[episode.config.policy]}
                    </span>
                    <span className="tag muted">
                      Seed {episode.config.seed}
                    </span>
                    {episode.config.runtime !== "none" && (
                      <span
                        className="tag model-tag"
                        title={`${episode.config.runtime} · ${episode.config.model}`}
                      >
                        {episode.config.model}
                      </span>
                    )}
                    <span className="episode-mode">
                      {episode.config.mode === "approval"
                        ? "Human approval"
                        : "Autonomous research"}
                    </span>
                  </div>
                  <div className="run-controls">
                    <span className="day-label">
                      DAY <b>{String(episode.day).padStart(2, "0")}</b> /{" "}
                      {episode.config.days}
                    </span>
                    <button
                      className="secondary small"
                      onClick={step}
                      disabled={busy || episode.status !== "ready"}
                    >
                      Step <ChevronRight size={15} />
                    </button>
                    {running ? (
                      <button
                        className="primary small"
                        onClick={() => {
                          stop.current = true;
                        }}
                      >
                        <Pause size={14} />
                        Pause
                      </button>
                    ) : (
                      <button
                        className="primary small"
                        onClick={run}
                        disabled={busy || episode.status !== "ready"}
                      >
                        <Play size={14} />
                        {episode.status === "completed"
                          ? "Completed"
                          : "Run episode"}
                      </button>
                    )}
                  </div>
                </div>
              )}
              {!episode && page !== "Architecture" && (
                <div className="empty-start">
                  <FlaskConical size={28} />
                  <h2>Your network is ready.</h2>
                  <p>
                    Create an episode to run {network?.sku_count || 200} SKUs
                    through a reproducible supply-chain simulation.
                  </p>
                  <button
                    className="primary"
                    onClick={() => setShowCreate(true)}
                  >
                    <Plus size={16} />
                    Create first episode
                  </button>
                </div>
              )}
              {episode?.pending && (
                <section className="approval-panel">
                  <div>
                    <span className="eyebrow">OPERATOR REVIEW REQUIRED</span>
                    <h2>
                      Day {episode.day + 1}: {episode.pending.actions.length}{" "}
                      proposed replenishment actions
                    </h2>
                    <p>
                      Inventory has not changed. Approve the plan, or reject
                      replenishment and advance demand for this day.
                    </p>
                  </div>
                  <div className="button-row">
                    <button
                      className="secondary"
                      onClick={() =>
                        setDetail({
                          title: "Pending plan · review all proposed actions",
                          value: episode.pending,
                        })
                      }
                    >
                      Review evidence
                    </button>
                    <button
                      className="secondary"
                      disabled={busy}
                      onClick={() => approve(false)}
                    >
                      Reject plan
                    </button>
                    <button
                      className="primary"
                      disabled={busy}
                      onClick={() => approve(true)}
                    >
                      <Check size={16} />
                      Approve & advance
                    </button>
                  </div>
                </section>
              )}
              {page === "Operations" && (
                <>
                  <section
                    className="kpi-grid"
                    aria-label="Measured performance"
                  >
                    <Metric
                      label="Demand fill rate"
                      value={percent(k?.service_level)}
                      icon={<ShieldCheck size={17} />}
                      detail={`${number(k?.total_filled)} / ${number(k?.total_demand)} units served`}
                      accent
                    />
                    <Metric
                      label="Total modeled cost"
                      value={money(k?.total_cost)}
                      icon={<Layers3 size={17} />}
                      detail="Purchasing + freight + holding + lost sales"
                    />
                    <Metric
                      label="Working capital"
                      value={money(k?.working_capital)}
                      icon={<Box size={17} />}
                      detail={`${number(k?.on_hand_units)} on hand · ${number(k?.open_orders)} open orders`}
                    />
                    <Metric
                      label="Lost demand"
                      value={number(k?.lost_units)}
                      icon={<Truck size={17} />}
                      detail={`${percent(k?.stockout_frequency)} of demand lines stocked out`}
                    />
                  </section>
                  <div className="operations-grid">
                    <section className="panel performance">
                      <PanelTitle
                        title="Service & cost trajectory"
                        note="COMPUTED"
                      />
                      <div className="chart-key">
                        <span>
                          <i className="cyan-line" />
                          Cumulative fill rate
                        </span>
                        <span>
                          <i className="blue-line" />
                          Cumulative cost
                        </span>
                        <span className="right">
                          {episode?.day || 0} observed days
                        </span>
                      </div>
                      <Chart history={episode?.history || []} />
                      <div className="chart-footer">
                        <span>
                          <ShieldCheck size={14} />
                          Calculated by the simulation engine
                        </span>
                        <span>
                          {episode?.config.runtime === "none"
                            ? "No LLM required"
                            : "Local-model assisted"}
                        </span>
                      </div>
                    </section>
                    {network && (
                      <Suspense
                        fallback={
                          <section className="panel scene-loading">
                            Preparing network visualization…
                          </section>
                        }
                      >
                        <NetworkScene
                          network={network}
                          day={episode?.day || 0}
                          onInspect={(warehouse) =>
                            setDetail({
                              title: `${warehouse.name} · warehouse evidence`,
                              value: warehouse,
                            })
                          }
                        />
                      </Suspense>
                    )}
                  </div>
                  <div className="operations-bottom">
                    <section className="panel">
                      <PanelTitle
                        title="Agent activity"
                        action={
                          <button
                            className="text-button"
                            onClick={() => setPage("Agent ledger")}
                          >
                            Open ledger <ArrowRight size={14} />
                          </button>
                        }
                      />
                      {latest?.decisions.length ? (
                        <div className="activity-list">
                          {latest.decisions.slice(0, 6).map((d, i) => (
                            <button
                              className="activity-row"
                              key={d.id}
                              onClick={() =>
                                setDetail({
                                  title: `${d.agent.replaceAll("_", " ")} · decision evidence`,
                                  value: d,
                                })
                              }
                            >
                              <span className={`agent-glyph agent-${i}`}>
                                <Activity size={16} />
                              </span>
                              <div>
                                <b>{d.agent.replaceAll("_", " ")}</b>
                                <span>{d.tool.replaceAll("_", " ")}</span>
                              </div>
                              <span
                                className={`pill ${d.status === "fallback" ? "warn" : ""}`}
                              >
                                {d.status}
                              </span>
                              <ChevronRight size={16} />
                            </button>
                          ))}
                        </div>
                      ) : (
                        <div className="empty">
                          {episode?.config.policy !== "agents" && episode
                            ? "This baseline runs without specialist agents."
                            : "Advance an agent episode to inspect its six specialist decisions."}
                        </div>
                      )}
                      <div className="panel-footer">
                        <Clock3 size={14} />
                        {latest
                          ? `${latest.telemetry.latency_ms.toFixed(1)} ms planning latency · ${latest.telemetry.runtime === "none" ? "deterministic tools" : latest.telemetry.model}`
                          : "Decision telemetry appears after the first day."}
                      </div>
                    </section>
                    <section className="panel">
                      <PanelTitle
                        title="Disruption calendar"
                        note="SCENARIO INPUT"
                      />
                      <div className="incident-list">
                        {network?.disruptions.map((d) => {
                          const day = episode?.day || 0;
                          const state =
                            day < d.start_day
                              ? "Upcoming"
                              : day < d.start_day + d.duration
                                ? "Active"
                                : "Resolved";
                          return (
                            <button
                              key={d.id}
                              className="incident-row"
                              onClick={() =>
                                setDetail({
                                  title: "Scenario disruption · ground truth",
                                  value: d,
                                })
                              }
                            >
                              <span
                                className={`incident-day ${state === "Active" ? "warn" : ""}`}
                              >
                                D{String(d.start_day + 1).padStart(2, "0")}
                              </span>
                              <div>
                                <b>{d.kind.replaceAll("_", " ")}</b>
                                <span>
                                  {d.target_id} · {d.duration} days
                                </span>
                              </div>
                              <span
                                className={`pill ${state === "Active" ? "warn" : "neutral"}`}
                              >
                                {state}
                              </span>
                            </button>
                          );
                        })}
                      </div>
                      <div className="panel-footer">
                        <CircleHelp size={14} />
                        Calendar shows seeded scenario events, including future
                        events.
                      </div>
                    </section>
                  </div>
                </>
              )}
              {page === "Inventory" && episode && (
                <InventoryView
                  warehouses={network?.warehouses || []}
                  episode={episode}
                  onInspect={(value) =>
                    setDetail({
                      title: "Inventory observation · computed evidence",
                      value,
                    })
                  }
                  onError={setError}
                />
              )}
              {page === "Agent ledger" && episode && (
                <section className="panel">
                  <PanelTitle
                    title="Decision timeline"
                    note={`${frames.length} RECORDED DAYS`}
                  />
                  {frames.length ? (
                    frames
                      .slice()
                      .reverse()
                      .map((f) => (
                        <div key={f.day} className="ledger-day">
                          <div className="ledger-day-header">
                            <h3>Day {f.day + 1}</h3>
                            <span className="tag">
                              {f.telemetry.runtime === "none"
                                ? "Deterministic"
                                : f.telemetry.model}
                            </span>
                            <span>{f.telemetry.latency_ms.toFixed(1)} ms</span>
                            <button
                              className="text-button"
                              onClick={() => inspect(f.day)}
                            >
                              Full evidence & ledger <ArrowRight size={14} />
                            </button>
                          </div>
                          <div className="decision-grid">
                            {f.decisions.map((d) => (
                              <DecisionCard
                                key={d.id}
                                decision={d}
                                onClick={() =>
                                  setDetail({
                                    title: "Decision evidence",
                                    value: d,
                                  })
                                }
                              />
                            ))}
                          </div>
                          <div className="ledger-summary">
                            {
                              f.outcomes.filter((o) => o.accepted_quantity > 0)
                                .length
                            }{" "}
                            orders dispatched ·{" "}
                            {
                              f.outcomes.filter((o) => o.status === "deferred")
                                .length
                            }{" "}
                            deferred by limits · {f.approval}
                            {f.telemetry.fallback && (
                              <span className="pill warn">
                                Model failure · safe fallback
                              </span>
                            )}
                          </div>
                        </div>
                      ))
                  ) : (
                    <div className="empty">
                      No decisions recorded. Advance the episode to begin.
                    </div>
                  )}
                </section>
              )}
              {page === "Experiments" && (
                <Experiments
                  current={episode}
                  onSelect={(id) =>
                    work(async () => {
                      await selectEpisode(id);
                      setPage("Operations");
                    })
                  }
                  onError={setError}
                  onReplay={(id) =>
                    work(async () => {
                      const result = await api<{
                        verified: boolean;
                        days_replayed: number;
                      }>(`/episodes/${id}/replay`);
                      setNotice(
                        result.verified
                          ? `Replay verified: all ${result.days_replayed} daily states match their recorded hashes.`
                          : "Replay mismatch detected. Inspect the exported episode.",
                      );
                    })
                  }
                  onExport={(id) =>
                    work(async () =>
                      download(
                        `episode-${id}.json`,
                        await api(`/episodes/${id}/export`),
                      ),
                    )
                  }
                />
              )}
              {page === "Data & provenance" && (
                <DataView
                  network={network}
                  onError={setError}
                  onInspect={(value) =>
                    setDetail({ title: "Validation report", value })
                  }
                />
              )}
              {page === "Architecture" && <Architecture />}
            </>
          )}
          <footer className="footer">
            <span>
              <ShieldCheck size={14} />
              Synthetic data · real calculations · reproducible decisions
            </span>
            <span>Research simulation / not a production planning system</span>
          </footer>
        </div>
      </main>
      {showCreate && (
        <CreateModal
          busy={busy}
          onClose={() => setShowCreate(false)}
          onCreate={newEpisode}
          defaultDataset={network?.id}
        />
      )}
      {showSettings && (
        <Modal title="Lab settings" onClose={() => setShowSettings(false)}>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const value = new FormData(e.currentTarget).get(
                "token",
              ) as string;
              sessionStorage.setItem("lab-operator-token", value);
              setShowSettings(false);
              setNotice("Operator token saved for this browser session.");
            }}
          >
            <label>
              Operator token
              <input
                type="password"
                name="token"
                defaultValue={getToken()}
                autoComplete="off"
              />
            </label>
            <p className="help">
              The local demo uses local-demo-token. Set WRITE_TOKEN on the
              server and enter the same value here to change it. Tokens stay in
              this browser session.
            </p>
            <button className="primary" type="submit">
              Save settings
            </button>
          </form>
        </Modal>
      )}
      {detail && (
        <Modal title={detail.title} onClose={() => setDetail(null)}>
          <div className="evidence-label">
            <ShieldCheck size={15} />
            Persisted or computed evidence · JSON export available
          </div>
          <pre className="evidence">
            {JSON.stringify(detail.value, null, 2)}
          </pre>
          <button
            className="secondary"
            onClick={() => download("evidence.json", detail.value)}
          >
            <ArrowDownToLine size={16} />
            Export evidence
          </button>
        </Modal>
      )}
    </div>
  );
}
