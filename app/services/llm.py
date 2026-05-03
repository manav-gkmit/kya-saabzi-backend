import logging
from google import genai
from google.genai import errors
from pydantic import BaseModel, Field, ValidationError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import settings

logger = logging.getLogger(__name__)

class DishEnrichmentResult(BaseModel):
    ingredients: list[str] = Field(description="List of 5-8 core ingredients for the dish, normalized to lowercase.")
    prep_time_minutes: int | None = Field(description="Estimated prep and cook time combined in minutes")
    calories_estimate: int | None = Field(description="Estimated calories per serving")

@retry(
    retry=retry_if_exception_type(errors.APIError),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(4),
    reraise=True,
)
def enrich_dish_with_gemini(dish_name: str) -> DishEnrichmentResult | None:
    """Uses Google Gemini to fetch default ingredients, prep time, and calories for a given dish."""
    if not settings.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not configured. Skipping enrichment.")
        return None
        
    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY.get_secret_value())
        prompt = f"Provide the core ingredients, estimated combined prep and cook time in minutes, and estimated calories per serving for the dish '{dish_name}'."
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config={
                'response_mime_type': 'application/json',
                'response_schema': DishEnrichmentResult,
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
            logger.warning("Gemini API error (rate limit / server error), retrying for dish '%s': %s", dish_name, e)
            raise e
        logger.exception("Unexpected error enriching dish '%s': %s", dish_name, e)
        return None


class IngredientStandardizationResult(BaseModel):
    standardized_ingredients: list[str] = Field(description="List of corrected and standardized ingredients, normalized to lowercase.")

@retry(
    retry=retry_if_exception_type(errors.APIError),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(4),
    reraise=True,
)
def standardize_ingredients_with_gemini(ingredients: list[str]) -> list[str]:
    """Uses Google Gemini to fix misspellings and standardize a list of ingredients."""
    if not ingredients:
        return []
        
    if not settings.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not configured. Skipping ingredient standardization.")
        return [i.strip().lower() for i in ingredients]
        
    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY.get_secret_value())
        prompt = f"Correct any spelling mistakes and standardize the following list of culinary ingredients into common base names: {ingredients}. Output a clean list of ingredients."
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config={
                'response_mime_type': 'application/json',
                'response_schema': IngredientStandardizationResult,
            },
        )
        if not response or not response.text:
            logger.warning("Gemini blocked/returned empty response for ingredients")
            return [i.strip().lower() for i in ingredients]
            
        result = IngredientStandardizationResult.model_validate_json(response.text)
        return result.standardized_ingredients
    except ValidationError as e:
        logger.error("Gemini returned invalid JSON schema for ingredients: %s", e)
        return [i.strip().lower() for i in ingredients]
    except Exception as e:
        if isinstance(e, errors.APIError):
            logger.warning("Gemini API error (rate limit / server error), retrying for ingredients: %s", e)
            raise e
        logger.exception("Unexpected error standardizing ingredients: %s", e)
        return [i.strip().lower() for i in ingredients]
