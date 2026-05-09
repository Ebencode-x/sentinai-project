"""Dummy vulnerable app for SentinAI demos."""

from __future__ import annotations

import logging
import random

from fastapi import FastAPI, HTTPException

app = FastAPI(title="Vulnerable Demo App", version="0.1.0")

logging.basicConfig(
    filename="logs/app.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

logger = logging.getLogger(__name__)


@app.get("/")
def root() -> dict[str, str]:
    logger.info("Health check route called.")
    return {"message": "Demo app is running"}


@app.get("/boom")
def boom() -> dict[str, str]:
    if random.random() < 0.7:
        try:
            # Intentionally crash for demo traffic.
            _ = 1 / 0
        except ZeroDivisionError:
            logger.exception("EXCEPTION simulated crash in /boom")
            raise HTTPException(status_code=500, detail="Simulated internal error")

    logger.info("Request succeeded without crash")
    return {"status": "ok"}
