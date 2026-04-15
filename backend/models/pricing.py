"""Pydantic models for per-provider scraped data.

These types are the intermediate shape produced by backend/providers/*
and consumed by services/offering_merger.py before being projected
into the v2 entity/offering model. They are not serialized to disk or
exposed on the API — models/v2.py is the API contract.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class Pricing(BaseModel):
    """Price info (USD per million tokens/units)."""

    input: Optional[float] = None
    output: Optional[float] = None
    cached_input: Optional[float] = None
    cached_write: Optional[float] = None
    reasoning: Optional[float] = None
    image_input: Optional[float] = None
    audio_input: Optional[float] = None
    audio_output: Optional[float] = None
    embedding: Optional[float] = None


class BatchPricing(BaseModel):
    """Batch processing discounted prices."""

    input: Optional[float] = None
    output: Optional[float] = None


class ModelPricing(BaseModel):
    """Complete pricing info for a single scraped model."""

    id: str  # Unique: "{provider}:{model_id}"
    provider: str  # aws_bedrock, openai, azure, etc.
    model_id: str  # Original model ID
    model_name: str  # Display name
    pricing: Pricing
    batch_pricing: Optional[BatchPricing] = None
    context_length: Optional[int] = None
    max_output_tokens: Optional[int] = None
    is_open_source: Optional[bool] = None  # True if weights are downloadable
    capabilities: List[str] = []  # ["text", "vision", "audio", "embedding"]
    input_modalities: List[str] = []  # ["text", "image", "audio", "video", "file"]
    output_modalities: List[str] = []  # ["text", "image", "audio", "video", "embedding"]
    last_updated: datetime
