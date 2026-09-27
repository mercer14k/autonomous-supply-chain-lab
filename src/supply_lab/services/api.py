import json
import logging
import os
import re
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import Field
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from supply_lab.ai.adapters import ModelCatalog, Runtime, list_local_models
from supply_lab.data.validation import MAX_UPLOAD
from supply_lab.domain.engine import forecast
from supply_lab.domain.models import EpisodeConfig, State, StrictModel
from supply_lab.services.store import Conflict, DatasetRow, EpisodeRow, NotFound, ReportRow, Store

logger = logging.getLogger("supply_lab")


class CreateEpisode(StrictModel):
    config: EpisodeConfig = Field(default_factory=EpisodeConfig)
    dataset_id: str | None = None


class Approval(StrictModel):
    approve: bool


class Page(StrictModel):
    items: list[dict]
    total: int
    offset: int
    limit: int


class EpisodeView(StrictModel):
    id: str
    dataset_id: str
    created_at: str
    config: EpisodeConfig
    day: int
    status: Literal["ready", "awaiting_approval", "completed"]
    kpis: dict
    history: list[dict]
    pending: dict | None
    engine_version: str
    version: int


class BodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in {"POST", "PUT", "PATCH"}:
            return await self.app(scope, receive, send)
        chunks, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            size += len(message.get("body", b""))
            if size > MAX_UPLOAD + 65536:
                return await JSONResponse(
                    {
                        "error": {
                            "code": "too_large",
                            "message": "Request exceeds 10 MiB",
                            "trace_id": str(uuid4()),
                        }
                    },
                    status_code=413,
                )(scope, receive, send)
            chunks.append(message.get("body", b""))
            if not message.get("more_body"):
                break
        delivered = False

        async def buffered():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return await receive()

        await self.app(scope, buffered, send)


def create_app(store: Store | None = None):
    db = store or Store()

    @asynccontextmanager
    async def lifespan(_):
        db.initialize()
        yield

    app = FastAPI(
        title="Autonomous Supply Chain Lab",
        version="0.1.0",
        lifespan=lifespan,
        description="Local research API. All monetary calculations use cents. Versioned routes: /api/v1.",
    )
    app.state.store = db
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "api", "testserver"])
    app.add_middleware(BodyLimit)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
    )

    @app.middleware("http")
    async def trace(request, call_next):
        request.state.trace_id = str(uuid4())
        start = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Trace-ID"] = request.state.trace_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        logger.info(
            json.dumps(
                {
                    "trace_id": request.state.trace_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "latency_ms": round((time.perf_counter() - start) * 1000, 2),
                }
            )
        )
        return response

    def error(request, status, code, message, **extra):
        return JSONResponse(
            {
                "error": {
                    "code": code,
                    "message": message,
                    "trace_id": getattr(request.state, "trace_id", "unavailable"),
                    **extra,
                }
            },
            status_code=status,
        )

    @app.exception_handler(NotFound)
    async def not_found(request, exc):
        return error(request, 404, "not_found", str(exc))

    @app.exception_handler(Conflict)
    @app.exception_handler(StaleDataError)
    @app.exception_handler(IntegrityError)
    async def conflict(request, exc):
        return error(
            request,
            409,
            "conflict",
            str(exc) if isinstance(exc, Conflict) else "Concurrent update; refresh and retry",
        )

    @app.exception_handler(RequestValidationError)
    async def validation(request, exc):
        return error(
            request,
            422,
            "invalid_request",
            "Request failed schema validation",
            details=[{"location": list(e["loc"]), "message": e["msg"]} for e in exc.errors()],
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request, exc):
        return error(request, exc.status_code, "request_rejected", exc.detail)

    @app.exception_handler(Exception)
    async def unexpected_error(request, exc):
        logger.error(
            json.dumps(
                {
                    "trace_id": getattr(request.state, "trace_id", "unavailable"),
                    "error_type": type(exc).__name__,
                }
            )
        )
        return error(
            request, 500, "internal_error", "Unexpected server error; inspect the trace ID in local logs"
        )

    def token(authorization: Annotated[str | None, Header()] = None):
        return authorization.removeprefix("Bearer ") if authorization else ""

    def writer(value: str = Depends(token)):
        expected = os.getenv("WRITE_TOKEN", "local-demo-token")
        if not expected or not secrets.compare_digest(value, expected):
            raise HTTPException(403, "An operator token is required for mutations")

    def reader(value: str = Depends(token)):
        expected = os.getenv("READ_TOKEN", "")
        if expected and not (
            secrets.compare_digest(value, expected)
            or secrets.compare_digest(value, os.getenv("WRITE_TOKEN", "local-demo-token"))
        ):
            raise HTTPException(403, "A reader or operator token is required")

    def request_key(value: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=100)]):
        if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
            raise HTTPException(422, "Invalid idempotency key")
        return value

    def page(items, offset, limit):
        return {
            "items": items[offset : offset + limit],
            "total": len(items),
            "offset": offset,
            "limit": limit,
        }

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/ready")
    def ready():
        try:
            with db.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return {"status": "ready"}
        except Exception:
            raise HTTPException(503, "Database unavailable") from None

    @app.get("/api/v1/models", response_model=ModelCatalog, dependencies=[Depends(reader)])
    def models(runtime: Runtime = Query(...)):
        return list_local_models(runtime)

    @app.get("/api/v1/datasets", response_model=Page, dependencies=[Depends(reader)])
    def datasets(offset: int = Query(0, ge=0), limit: int = Query(30, ge=1, le=200)):
        with db.Session() as session:
            rows = list(
                session.scalars(select(DatasetRow).order_by(DatasetRow.id).offset(offset).limit(limit))
            )
            total = session.scalar(select(func.count()).select_from(DatasetRow))
            return {
                "items": [
                    {"id": r.id, "sku_count": len(r.payload["skus"]), "report": r.report} for r in rows
                ],
                "total": total,
                "offset": offset,
                "limit": limit,
            }

    @app.get("/api/v1/network", dependencies=[Depends(reader)])
    def network(dataset_id: str | None = None):
        data, report = db.dataset(dataset_id)
        return {
            "id": data.id,
            "suppliers": [s.model_dump() for s in data.suppliers],
            "plants": [p.model_dump() for p in data.plants],
            "warehouses": [w.model_dump() for w in data.warehouses],
            "markets": [m.model_dump() for m in data.markets],
            "sku_count": len(data.skus),
            "disruptions": [d.model_dump() for d in data.disruptions],
            "validation": report,
        }

    @app.post("/api/v1/datasets/import", dependencies=[Depends(writer)])
    async def import_dataset(request: Request, file: UploadFile = File(...)):
        if file.content_type != "application/json":
            raise HTTPException(415, "Upload a JSON dataset with application/json MIME type")
        raw = await file.read(MAX_UPLOAD + 1)
        filename = re.sub(r"[^A-Za-z0-9._-]", "_", Path(file.filename or "dataset.json").name)[:100]
        report = db.ingest(raw, filename)
        if not report["accepted"]:
            return error(
                request,
                422,
                "invalid_dataset",
                "Dataset rejected; inspect the validation report",
                report=report,
            )
        return JSONResponse(report, status_code=201)

    @app.get("/api/v1/validation-reports/{identifier}", dependencies=[Depends(reader)])
    def report(identifier: str):
        with db.Session() as session:
            row = session.get(ReportRow, identifier)
            if not row:
                raise NotFound("Validation report not found")
            return row.payload

    @app.get("/api/v1/episodes", response_model=Page, dependencies=[Depends(reader)])
    def episodes(offset: int = Query(0, ge=0), limit: int = Query(30, ge=1, le=200)):
        with db.Session() as session:
            rows = session.scalars(
                select(EpisodeRow).order_by(EpisodeRow.created_at.desc()).offset(offset).limit(limit)
            )
            total = session.scalar(select(func.count()).select_from(EpisodeRow))
            return {
                "items": [
                    {
                        "id": e.id,
                        "created_at": e.created_at,
                        "config": e.config,
                        "day": e.state["day"],
                        "dataset_id": e.dataset_id,
                    }
                    for e in rows
                ],
                "total": total,
                "offset": offset,
                "limit": limit,
            }

    @app.post("/api/v1/episodes", response_model=EpisodeView, status_code=201, dependencies=[Depends(writer)])
    def create(body: CreateEpisode, request_id: str = Depends(request_key)):
        return db.create(body.config, body.dataset_id, request_id)

    @app.get("/api/v1/episodes/{identifier}", response_model=EpisodeView, dependencies=[Depends(reader)])
    def episode(identifier: str):
        return db.view(db.get_episode(identifier))

    @app.post(
        "/api/v1/episodes/{identifier}/step", response_model=EpisodeView, dependencies=[Depends(writer)]
    )
    def step(identifier: str, request: Request, request_id: str = Depends(request_key)):
        return db.step(identifier, request_id, trace_id=request.state.trace_id)

    @app.post(
        "/api/v1/episodes/{identifier}/approval", response_model=EpisodeView, dependencies=[Depends(writer)]
    )
    def approval(identifier: str, body: Approval, request: Request, request_id: str = Depends(request_key)):
        return db.step(identifier, request_id, body.approve, trace_id=request.state.trace_id)

    @app.get("/api/v1/episodes/{identifier}/inventory", response_model=Page, dependencies=[Depends(reader)])
    def inventory(
        identifier: str,
        q: str = Query("", max_length=100),
        warehouse: str = "",
        at_risk: bool = False,
        offset: int = Query(0, ge=0),
        limit: int = Query(30, ge=1, le=200),
    ):
        ep = db.get_episode(identifier)
        rows = forecast(db.dataset(ep.dataset_id)[0], State.model_validate(ep.state))
        rows = [
            r
            for r in rows
            if (q.lower() in (r["sku_id"] + r["name"]).lower())
            and (not warehouse or r["warehouse_id"] == warehouse)
            and (not at_risk or (r["daily_forecast"] and r["days_cover"] < r["lead_days"]))
        ]
        return page(rows, offset, limit)

    @app.get("/api/v1/episodes/{identifier}/orders", response_model=Page, dependencies=[Depends(reader)])
    def orders(identifier: str, offset: int = Query(0, ge=0), limit: int = Query(30, ge=1, le=200)):
        ep = db.get_episode(identifier)
        return page(list(reversed(ep.state["orders"])), offset, limit)

    @app.get("/api/v1/episodes/{identifier}/frames", response_model=Page, dependencies=[Depends(reader)])
    def frames(identifier: str, offset: int = Query(0, ge=0), limit: int = Query(30, ge=1, le=200)):
        return page(
            [{k: v for k, v in f.payload.items() if k != "ledger"} for f in db.frames(identifier)],
            offset,
            limit,
        )

    @app.get("/api/v1/episodes/{identifier}/frames/{day}", dependencies=[Depends(reader)])
    def frame(identifier: str, day: int):
        found = next((f for f in db.frames(identifier) if f.day == day), None)
        if not found:
            raise NotFound("Frame not found")
        return found.payload

    @app.get("/api/v1/episodes/{identifier}/replay", dependencies=[Depends(reader)])
    def replay(identifier: str):
        return db.replay(identifier)

    @app.get("/api/v1/episodes/{identifier}/export", dependencies=[Depends(reader)])
    def export(identifier: str):
        ep = db.get_episode(identifier)
        payload = {
            "episode": db.view(ep),
            "dataset": db.dataset(ep.dataset_id)[0].model_dump(),
            "state": ep.state,
            "frames": [{"payload": f.payload, "state_hash": f.state_hash} for f in db.frames(identifier)],
        }
        return Response(
            json.dumps(payload),
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="episode.json"'},
        )

    return app
