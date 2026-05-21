from __future__ import annotations

import logging
from functools import lru_cache

from google import genai
from google.genai import errors
from pydantic import BaseModel, Field, ValidationError
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_gemini_client() -> genai.Client | None:
    """Return a reusable Gemini client, or None if the key is not set."""
    if not settings.GEMINI_API_KEY:
        return None
    return genai.Client(api_key=settings.GEMINI_API_KEY.get_secret_value())


def is_transient_error(exc: BaseException) -> bool:
    """Return True if the error is a server error or a rate limit (429)."""
    if hasattr(errors, "ServerError") and isinstance(exc, errors.ServerError):
        return True
    if hasattr(errors, "RateLimitError") and isinstance(exc, errors.RateLimitError):
        return True
    if isinstance(exc, errors.APIError):
        # google-genai may expose `code` or `status_code`
        status = getattr(exc, "status_code", getattr(exc, "code", None))
        if status == 429:
            return True
    return False


class DishEnrichmentResult(BaseModel):
    ingredients: list[str] = Field(
        description="List of 5-8 core ingredients for the dish, normalized to lowercase."
    )
    prep_time_minutes: int | None = Field(
        description="Estimated prep and cook time combined in minutes"
    )
    calories_estimate: int | None = Field(description="Estimated calories per serving")


@retry(
    retry=retry_if_exception(is_transient_error),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(4),
    reraise=True,
)
def enrich_dish_with_gemini(dish_name: str) -> DishEnrichmentResult | None:
    """Uses Google Gemini to fetch default ingredients, prep time, and calories for a given dish."""
    client = _get_gemini_client()
    if client is None:
        logger.warning("GEMINI_API_KEY not configured. Skipping enrichment.")
        return None

    try:
        prompt = f"Provide the core ingredients, estimated combined prep and cook time in minutes, and estimated calories per serving for the dish '{dish_name}'."

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": DishEnrichmentResult,
            },
        )
        if not response or not response.text:
            logger.warning("Gemini blocked/returned empty response for dish '%s'", dish_name)
            return None

        return DishEnrichmentResult.model_validate_json(response.text)
    except ValidationError as e:
        logger.error("Gemini returned invalid JSON schema for dish '%s': %s", dish_name, e)
        return None
    except Exception as e:
        if isinstance(e, errors.APIError):
            logger.warning(
                "Gemini API error (rate limit / server error), retrying for dish '%s': %s",
                dish_name,
                e,
            )
            raise e
        logger.exception("Unexpected error enriching dish '%s': %s", dish_name, e)
        return None


@retry(
    retry=retry_if_exception(is_transient_error),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(4),
    reraise=True,
)
async def enrich_dish_with_gemini_async(dish_name: str) -> DishEnrichmentResult | None:
    """Uses Google Gemini asynchronously to fetch default ingredients, prep time, and calories for a given dish."""
    client = _get_gemini_client()
    if client is None:
        logger.warning("GEMINI_API_KEY not configured. Skipping enrichment.")
        return None

    try:
        prompt = f"Provide the core ingredients, estimated combined prep and cook time in minutes, and estimated calories per serving for the dish '{dish_name}'."

        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": DishEnrichmentResult,
            },
        )
        if not response or not response.text:
            logger.warning("Gemini blocked/returned empty response for dish '%s'", dish_name)
            return None

        return DishEnrichmentResult.model_validate_json(response.text)
    except ValidationError as e:
        logger.error("Gemini returned invalid JSON schema for dish '%s': %s", dish_name, e)
        return None
    except Exception as e:
        if isinstance(e, errors.APIError):
            logger.warning(
                "Gemini API error (rate limit / server error), retrying for dish '%s': %s",
                dish_name,
                e,
            )
            raise e
        logger.exception("Unexpected error enriching dish '%s': %s", dish_name, e)
        return None

