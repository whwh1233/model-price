"""Data fetch orchestrator."""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from providers import ProviderRegistry
from .pricing import PricingService
from .metadata_fetcher import MetadataFetcher

logger = logging.getLogger(__name__)


class Fetcher:
    """Orchestrates fetching pricing data from all providers."""

    _refresh_lock: Optional[asyncio.Lock] = None

    @classmethod
    def _get_refresh_lock(cls) -> asyncio.Lock:
        """Lazily initialize a shared lock for refresh operations."""
        if cls._refresh_lock is None:
            cls._refresh_lock = asyncio.Lock()
        return cls._refresh_lock

    @classmethod
    async def refresh_all(cls, include_metadata: bool = True) -> dict:
        """Refresh data from all providers.

        Args:
            include_metadata: If True, also enrich models with metadata from LiteLLM.

        Uses grouped fetch to save each provider independently, which works
        better with the split-file storage format.
        """
        async with cls._get_refresh_lock():
            return await cls._refresh_all_unlocked(include_metadata=include_metadata)

    @classmethod
    async def _refresh_all_unlocked(cls, include_metadata: bool = True) -> dict:
        """Refresh data from all providers without acquiring the refresh lock."""
        logger.info("Starting full refresh...")
        start = datetime.now()

        # Fetch all providers concurrently, grouped by provider
        grouped = await ProviderRegistry.fetch_all_grouped()

        total_models = 0
        provider_stats = {}

        # Process and save each provider independently
        for provider_name, models in grouped.items():
            # Enrich with metadata
            if include_metadata:
                models = await MetadataFetcher.enrich_models(models)

            # Save this provider's models
            PricingService.update_provider(provider_name, models)

            provider_stats[provider_name] = len(models)
            total_models += len(models)

        elapsed = (datetime.now() - start).total_seconds()
        logger.info(f"Refresh complete: {total_models} models in {elapsed:.2f}s")

        return {
            "status": "ok",
            "models_count": total_models,
            "providers": provider_stats,
            "elapsed_seconds": elapsed,
            "timestamp": datetime.now().isoformat(),
        }

    @classmethod
    async def refresh_provider(cls, provider_name: str, include_metadata: bool = True) -> dict:
        """Refresh data from a single provider.

        Args:
            provider_name: The provider to refresh.
            include_metadata: If True, also enrich models with metadata from LiteLLM.
        """
        async with cls._get_refresh_lock():
            return await cls._refresh_provider_unlocked(
                provider_name=provider_name,
                include_metadata=include_metadata,
            )

    @classmethod
    async def _refresh_provider_unlocked(
        cls,
        provider_name: str,
        include_metadata: bool = True,
    ) -> dict:
        """Refresh one provider without acquiring the refresh lock."""
        logger.info(f"Refreshing provider: {provider_name}")
        start = datetime.now()

        models = await ProviderRegistry.fetch_provider(provider_name)

        # Enrich with metadata (context_length, max_output_tokens, is_open_source)
        if include_metadata:
            models = await MetadataFetcher.enrich_models(models)

        PricingService.update_provider(provider_name, models)

        elapsed = (datetime.now() - start).total_seconds()
        logger.info(f"Provider {provider_name}: {len(models)} models in {elapsed:.2f}s")

        return {
            "status": "ok",
            "provider": provider_name,
            "models_count": len(models),
            "elapsed_seconds": elapsed,
            "timestamp": datetime.now().isoformat(),
        }
