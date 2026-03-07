"""AI-Designed Carbon-Reducing Enzyme Platform — FastAPI application entrypoint."""
import gc
import warnings
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from enzyme.config import enzyme_settings
from enzyme.router import router as enzyme_router
from logging_config import logger, shutdown_logging

warnings.filterwarnings("ignore")

logger.info("Starting enzyme platform application...")


# ---------------- Lifespan ---------------- #
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "App starting up — conserved_positions_count: %d, max_mutation_threshold: %d, "
        "default_weights: bio=%.2f carbon=%.2f feasibility=%.2f",
        len(enzyme_settings.conserved_positions),
        enzyme_settings.max_mutation_threshold,
        enzyme_settings.bio_weight,
        enzyme_settings.carbon_weight,
        enzyme_settings.feasibility_weight,
    )
    yield

    logger.info("App shutting down...")
    try:
        gc.collect()
    finally:
        shutdown_logging()


# ---------------- App Setup ---------------- #
app = FastAPI(
    title="AI-Designed Carbon-Reducing Enzyme Platform",
    description=(
        "Mock enzyme mutation candidate generator and scorer. "
        "All scores are simulation proxies — not wet-lab validated predictions."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- Routers ---------------- #
app.include_router(enzyme_router)


# ---------------- Run ---------------- #
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
