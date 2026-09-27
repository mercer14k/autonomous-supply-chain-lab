import json
import os
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, ForeignKey, Integer, String, UniqueConstraint, create_engine, event, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

from supply_lab.ai.orchestrator import parse_actions, plan
from supply_lab.data.generator import generate
from supply_lab.data.validation import validate_bytes
from supply_lab.domain.engine import ENGINE_VERSION, advance, initial_state, kpis, state_hash
from supply_lab.domain.models import Dataset, EpisodeConfig, State


def now():
    return datetime.now(timezone.utc).isoformat()


class Base(DeclarativeBase):
    pass


class DatasetRow(Base):
    __tablename__ = "datasets"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)
    report: Mapped[dict] = mapped_column(JSON)


class ReportRow(Base):
    __tablename__ = "validation_reports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)


class EpisodeRow(Base):
    __tablename__ = "episodes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id"))
    created_at: Mapped[str] = mapped_column(String(40))
    config: Mapped[dict] = mapped_column(JSON)
    state: Mapped[dict] = mapped_column(JSON)
    pending: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    __mapper_args__ = {"version_id_col": version}


class FrameRow(Base):
    __tablename__ = "frames"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    episode_id: Mapped[str] = mapped_column(ForeignKey("episodes.id"), index=True)
    day: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSON)
    state_hash: Mapped[str] = mapped_column(String(64))
    __table_args__ = (UniqueConstraint("episode_id", "day"),)


class CommandRow(Base):
    __tablename__ = "commands"
    id: Mapped[str] = mapped_column(String(180), primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64))
    response: Mapped[dict] = mapped_column(JSON)


class Conflict(Exception):
    pass


class NotFound(Exception):
    pass


class Store:
    def __init__(self, url=None):
        url = url or os.getenv("DATABASE_URL", "sqlite:///./lab.db")
        kwargs = {"pool_pre_ping": True}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
            if ":memory:" in url:
                kwargs["poolclass"] = StaticPool
        self.engine = create_engine(url, **kwargs)
        if url.startswith("sqlite"):

            @event.listens_for(self.engine, "connect")
            def pragmas(connection, _):
                connection.execute("PRAGMA foreign_keys=ON")
                connection.execute("PRAGMA journal_mode=WAL")

        self.Session = sessionmaker(self.engine, expire_on_commit=False)

    def initialize(self):
        Base.metadata.create_all(self.engine)
        data = generate()
        with self.Session.begin() as session:
            if session.get(DatasetRow, data.id) is None:
                _, report = validate_bytes(data.model_dump_json().encode())
                session.add(DatasetRow(id=data.id, payload=data.model_dump(), report=report))

    def dataset(self, dataset_id=None):
        with self.Session() as session:
            row = session.get(DatasetRow, dataset_id or "synthetic-v1-seed-42-n-200")
            if not row:
                raise NotFound("Dataset not found")
            return Dataset.model_validate(row.payload), row.report

    def ingest(self, raw: bytes, filename: str):
        data, report = validate_bytes(raw)
        report_id = str(uuid4())
        report.update(id=report_id, filename=filename)
        with self.Session.begin() as session:
            if data:
                existing = session.get(DatasetRow, data.id)
                if existing and existing.payload != data.model_dump():
                    report["accepted"] = False
                    report["errors"].append(
                        {"location": "id", "message": "Dataset ID exists with different content"}
                    )
                elif not existing:
                    session.add(DatasetRow(id=data.id, payload=data.model_dump(), report=report))
            session.add(ReportRow(id=report_id, payload=report))
        return report

    def get_episode(self, identifier):
        with self.Session() as session:
            ep = session.get(EpisodeRow, identifier)
            if not ep:
                raise NotFound("Episode not found")
            return ep

    def view(self, ep: EpisodeRow, data: Dataset | None = None):
        data = data or self.dataset(ep.dataset_id)[0]
        state = State.model_validate(ep.state)
        return {
            "id": ep.id,
            "dataset_id": ep.dataset_id,
            "created_at": ep.created_at,
            "config": ep.config,
            "day": state.day,
            "status": "awaiting_approval"
            if ep.pending
            else ("completed" if state.day >= ep.config["days"] else "ready"),
            "kpis": kpis(state, data),
            "history": state.metrics,
            "pending": ep.pending,
            "engine_version": ENGINE_VERSION,
            "version": ep.version,
        }

    def command(self, command_id: str, payload: dict, operation):
        import hashlib

        fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        with self.Session.begin() as session:
            prior = session.get(CommandRow, command_id)
            if prior:
                if prior.fingerprint != fingerprint:
                    raise Conflict("Idempotency key was already used with a different request")
                return prior.response
            response = operation(session)
            session.add(CommandRow(id=command_id, fingerprint=fingerprint, response=response))
            return response

    def create(self, config: EpisodeConfig, dataset_id: str | None, request_key: str):
        data, _ = self.dataset(dataset_id)

        def operation(session):
            ep = EpisodeRow(
                id=str(uuid4()),
                dataset_id=data.id,
                created_at=now(),
                config=config.model_dump(),
                state=initial_state(data).model_dump(),
                pending=None,
            )
            session.add(ep)
            session.flush()
            return self.view(ep, data)

        return self.command(
            "create:" + request_key, {"config": config.model_dump(), "dataset": data.id}, operation
        )

    def step(
        self, identifier: str, request_key: str, approval: bool | None = None, trace_id: str | None = None
    ):
        def operation(session):
            ep = session.scalar(select(EpisodeRow).where(EpisodeRow.id == identifier).with_for_update())
            if not ep:
                raise NotFound("Episode not found")
            data = Dataset.model_validate(session.get(DatasetRow, ep.dataset_id).payload)
            state, config = State.model_validate(ep.state), EpisodeConfig.model_validate(ep.config)
            if state.day >= config.days:
                raise Conflict("Episode is already complete")
            if ep.pending:
                if approval is None:
                    raise Conflict("Approve or reject the pending plan before advancing")
                proposal = ep.pending
            else:
                if approval is not None:
                    raise Conflict("No pending plan to approve")
                proposal = plan(data, state, config)
                if config.mode == "approval":
                    ep.pending = proposal
                    session.flush()
                    return self.view(ep, data)
            actions = parse_actions(proposal) if approval is not False else []
            updated, frame = advance(data, state, config, actions)
            frame.update(
                episode_id=identifier,
                trace_id=trace_id or request_key,
                data_version=data.id,
                decisions=proposal["decisions"],
                telemetry=proposal["telemetry"],
                proposed_actions=proposal["actions"],
                approval="rejected" if approval is False else ("approved" if approval else "autonomous"),
                recorded_at=now(),
            )
            session.add(
                FrameRow(
                    id=f"{identifier}:{state.day}",
                    episode_id=identifier,
                    day=state.day,
                    payload=frame,
                    state_hash=state_hash(updated),
                )
            )
            ep.state, ep.pending = updated.model_dump(), None
            session.flush()
            return self.view(ep, data)

        return self.command(f"step:{identifier}:{request_key}", {"approval": approval}, operation)

    def frames(self, identifier):
        self.get_episode(identifier)
        with self.Session() as session:
            return list(
                session.scalars(
                    select(FrameRow).where(FrameRow.episode_id == identifier).order_by(FrameRow.day)
                )
            )

    def replay(self, identifier):
        ep = self.get_episode(identifier)
        data = self.dataset(ep.dataset_id)[0]
        config = EpisodeConfig.model_validate(ep.config)
        state = initial_state(data)
        checks = []
        for frame in self.frames(identifier):
            state, _ = advance(data, state, config, parse_actions(frame.payload))
            checks.append({"day": frame.day, "matches": state_hash(state) == frame.state_hash})
        final_matches = state_hash(state) == state_hash(State.model_validate(ep.state))
        return {
            "episode_id": identifier,
            "verified": all(c["matches"] for c in checks) and final_matches,
            "days_replayed": len(checks),
            "checks": checks,
            "final_state_matches": final_matches,
            "engine_version": ENGINE_VERSION,
            "state_hash": state_hash(state),
        }
