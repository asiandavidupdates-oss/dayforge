"""DayForge — one deployable FastAPI service serving API + frontend."""
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.responses import JSONResponse

from .database import Base, engine
from .routers import analytics, auth, days, goals, misc

Base.metadata.create_all(bind=engine)

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="DayForge", version="1.0.0")
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request, exc):
    return JSONResponse({"detail": "Rate limit exceeded, try again shortly."}, status_code=429)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to your public domain in production if desired
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(days.router)
app.include_router(goals.router)
app.include_router(analytics.router)
app.include_router(misc.router)

STATIC = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/health")
def health():
    return {"status": "ok", "app": "DayForge"}


@app.get("/")
def root():
    return FileResponse(STATIC / "index.html")


@app.middleware("http")
async def security_headers(request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    return resp
