import logging
from google import genai
from pydantic import BaseModel, Field

from app.config import settings

logger = logging.getLogger(__name__)

class DishEnrichmentResult(BaseModel):
    ingredients: list[str] = Field(description="List of 5-8 core ingredients for the dish, normalized to lowercase.")
    prep_time_minutes: int | None = Field(description="Estimated prep and cook time combined in minutes")
    calories_estimate: int | None = Field(description="Estimated calories per serving")

def enrich_dish_with_gemini(dish_name: str) -> DishEnrichmentResult | None:
    """Uses Google Gemini to fetch default ingredients, prep time, and calories for a given dish."""
    if not getattr(settings, "GEMINI_API_KEY", None):
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
        return DishEnrichmentResult.model_validate_json(response.text)
    except Exception as e:
        logger.error("Failed to enrich dish '%s' via Gemini: %s", dish_name, e)
        return None


class IngredientStandardizationResult(BaseModel):
    standardized_ingredients: list[str] = Field(description="List of corrected and standardized ingredients, normalized to lowercase.")

def standardize_ingredients_with_gemini(ingredients: list[str]) -> list[str]:
    """Uses Google Gemini to fix misspellings and standardize a list of ingredients."""
    if not ingredients:
        return []
        
    if not getattr(settings, "GEMINI_API_KEY", None):
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
        result = IngredientStandardizationResult.model_validate_json(response.text)
        return result.standardized_ingredients
    except Exception as e:
        logger.error("Failed to standardize ingredients via Gemini: %s", e)
        return [i.strip().lower() for i in ingredients]
