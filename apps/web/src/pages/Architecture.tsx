import {
  Database,
  Activity,
  ShieldCheck,
  GitBranch,
  Terminal,
  Zap,
  ArrowRight,
} from "lucide-react";
import { PanelTitle } from "../components/ui";

export function Architecture() {
  return (
    <div className="architecture">
      <section className="panel">
        <PanelTitle title="One auditable decision loop" note="ENGINE v1.0" />
        <div className="architecture-flow">
          {[
            {
              icon: Database,
              title: "Validated inputs",
              text: "Seeded network, demand priors, and disruption ground truth.",
            },
            {
              icon: Activity,
              title: "Specialist tools",
              text: "Demand, inventory, procurement, supplier risk, logistics, incidents.",
            },
            {
              icon: ShieldCheck,
              title: "Action validator",
              text: "Evidence, allowlisted actions, capacities, order multiples, and budget.",
            },
            {
              icon: GitBranch,
              title: "Deterministic engine",
              text: "Receipts, lost sales, inventory balances, cost, and service KPIs.",
            },
            {
              icon: Terminal,
              title: "Persist & replay",
              text: "Full daily ledger, observable telemetry, actions, and state hashes.",
            },
          ].map(({ icon: Icon, title, text }, i) => (
            <div className="architecture-step" key={title}>
              <span className="eyebrow">0{i + 1}</span>
              <Icon size={23} />
              <h3>{title}</h3>
              <p>{text}</p>
            </div>
          ))}
        </div>
      </section>
      <div className="architecture-notes">
        <section className="panel prose">
          <h2>What the models control</h2>
          <p>
            Optional Ollama, llama.cpp, and vLLM adapters select from
            deterministic order candidates for the twelve highest-priority
            inventory lines each day. All other lines use the documented
            heuristic.
          </p>
          <p>
            Model output cannot execute code or SQL, invent quantities, or write
            inventory. Missing evidence produces abstention. Invalid inference
            triggers an observable deterministic fallback.
          </p>
          <span className="pill">No paid API required</span>
        </section>
        <section className="panel prose">
          <h2>What the results mean</h2>
          <p>
            Fill rate is fulfilled units divided by demand. Working capital
            includes on-hand inventory and committed inbound orders. Cost
            combines procurement, transport, daily holding, and a modeled
            lost-sales penalty.
          </p>
          <p>
            This is a daily, single-stage assembly abstraction with fixed unit
            conversion, lost sales, and no terminal salvage credit. Compare
            equal horizons and seeds; these results are research evidence, not
            production planning recommendations.
          </p>
          <span className="pill neutral">Explicit assumptions</span>
        </section>
      </div>
      <section className="panel prose">
        <h2>Open source, end to end</h2>
        <p>
          Python · FastAPI · Pydantic · SQLAlchemy · PostgreSQL / SQLite · React
          · TypeScript · Apache ECharts. Docker Compose provides the complete
          local demo. Native macOS and Windows instructions, evaluation
          methodology, dependency licenses, and the threat model live in the
          repository documentation.
        </p>
        <div className="button-row">
          <a
            className="secondary"
            href="http://localhost:8000/docs"
            target="_blank"
            rel="noreferrer"
          >
            API documentation <ArrowRight size={16} />
          </a>
          <span className="help">
            <Zap size={15} />
            No-LLM mode works without any downloaded model.
          </span>
        </div>
      </section>
    </div>
  );
}
