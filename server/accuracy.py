"""Inference configuration; benchmark replay remains separate from live scans."""
from dataclasses import dataclass

BENCHMARK_URL = "https://atharva-729.github.io/bookshelf-benchmark/"
TILE_EDGE = 1400
OVERLAP = 0.20
MAX_TILES = 48


@dataclass(frozen=True)
class ModelProfile:
    provider: str
    model_id: str
    name: str
    effort: str
    reason: str


FOUNDRY_GEMINI = ModelProfile(
    "straive", "gemini-3.1-pro-preview", "Gemini 3.1 Pro Preview", "high",
    "Configured company inference route; not measured by the saved benchmark.",
)


def select_profile():
    # The gateway model has not been evaluated against the benchmark.
    return FOUNDRY_GEMINI
