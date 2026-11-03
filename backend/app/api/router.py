"""
API router – aggregates all route modules.
"""
from fastapi import APIRouter

from app.api.routes import audit, auth, cases, health, search, videos

api_router = APIRouter()

# ── Authentication & Identity (Phase 8) ─────────────────────────────────────
api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Auth"],
)

# ── Security Audit Trail (Phase 8) ──────────────────────────────────────────
api_router.include_router(
    audit.router,
    prefix="/audit",
    tags=["Audit"],
)

# ── Health ──────────────────────────────────────────────────────────────────
api_router.include_router(
    health.router,
    prefix="",
    tags=["Health"],
)

# ── Video Library ───────────────────────────────────────────────────────────
api_router.include_router(
    videos.router,
    prefix="/videos",
    tags=["Videos"],
)

# ── Natural Language CCTV Search (Phase 5) ──────────────────────────────────
api_router.include_router(
    search.router,
    prefix="/search",
    tags=["Search"],
)

# ── Investigation Cases & Evidence Management (Phase 7) ─────────────────────
api_router.include_router(
    cases.router,
    prefix="/cases",
    tags=["Cases"],
)

api_router.include_router(
    cases.router,
    prefix="/investigations",
    tags=["Investigations"],
)
