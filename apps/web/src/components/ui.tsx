import { useEffect, useRef } from "react";
import { X, ArrowRight } from "lucide-react";
import type { Decision } from "../types";

export function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    ref.current?.showModal();
  }, []);
  return (
    <dialog
      ref={ref}
      onCancel={onClose}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="dialog-head">
        <h2>{title}</h2>
        <button
          className="icon-button"
          aria-label="Close dialog"
          onClick={onClose}
        >
          <X size={20} />
        </button>
      </div>
      {children}
    </dialog>
  );
}

export function PanelTitle({
  title,
  note,
  action,
}: {
  title: string;
  note?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="panel-title">
      <h2>{title}</h2>
      {note && <span className="source-label">{note}</span>}
      {action}
    </div>
  );
}

export function Metric({
  label,
  value,
  detail,
  icon,
  accent = false,
}: {
  label: string;
  value: string;
  detail: string;
  icon: React.ReactNode;
  accent?: boolean;
}) {
  return (
    <article className={`metric ${accent ? "accent" : ""}`}>
      <div className="metric-label">
        {label}
        {icon}
      </div>
      <strong>{value}</strong>
      <p>{detail}</p>
    </article>
  );
}

export function DecisionCard({
  decision: d,
  onClick,
}: {
  decision: Decision;
  onClick: () => void;
}) {
  return (
    <button className="decision-card" onClick={onClick}>
      <div>
        <b>{d.agent.replaceAll("_", " ")}</b>
        <span className="source-label">
          {d.kind === "ai_narrative" ? "AI NARRATIVE" : "COMPUTED"}
        </span>
      </div>
      <code>{d.tool}</code>
      <p>
        {Object.entries(d.summary)
          .map(
            ([k, v]) =>
              `${k.replaceAll("_", " ")}: ${Array.isArray(v) ? v.length : typeof v === "object" ? JSON.stringify(v) : v}`,
          )
          .join(" · ")}
      </p>
      <span className="evidence-link">
        {d.evidence_ids.length} evidence sources <ArrowRight size={14} />
      </span>
    </button>
  );
}
