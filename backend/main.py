"""FastAPI entrypoint for the WC 2026 forecast API."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import matches, calibration

app = FastAPI(
    title="WC 2026 Forecast API",
    description="Probabilistic forecasts for the 2026 FIFA World Cup.",
    version="0.1.0",
)

# CORS — allow the Vercel frontend and local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://wc2026.vercel.app",
    ],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(matches.router)
app.include_router(calibration.router)


@app.get("/")
def root():
    return {"status": "ok", "service": "wc2026-forecast-api"}


@app.get("/health")
def health():
    return {"status": "healthy"}
