"""FastAPI application entry point."""
from __future__ import annotations

import logging
import logging.config
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from app.api import router
from app.config_loader import load_conserved_positions, load_weights_config

# Structured JSON-friendly logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Load and validate configuration on startup."""
    conserved_positions = load_conserved_positions()
    weights, max_mutation_threshold = load_weights_config()

    logger.info(
        '{"event": "startup", "conserved_positions_count": %d, '
        '"max_mutation_threshold": %d, '
        '"default_weights": {"bio": %.2f, "carbon": %.2f, "feasibility": %.2f}, '
        '"message": "Config loaded successfully"}',
        len(conserved_positions),
        max_mutation_threshold,
        weights.bio_weight,
        weights.carbon_weight,
        weights.feasibility_weight,
    )
    yield
    # Shutdown: nothing to clean up (stateless design)


app = FastAPI(
    title="AI-Designed Carbon-Reducing Enzyme Platform",
    description=(
        "Mock enzyme mutation candidate generator and scorer. "
        "All scores are simulation proxies — not wet-lab validated predictions."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(router)
