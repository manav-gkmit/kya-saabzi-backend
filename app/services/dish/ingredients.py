"""Ingredient attachment logic for dishes."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dishes import Dish, Ingredient


async def attach_ingredients_to_dish(
    db: AsyncSession, dish: Dish, ingredient_names: list[str]
) -> None:
    """Find or create ingredients by name and attach them to the given dish."""
    normalized_names = {name.lower().strip() for name in ingredient_names if name.strip()}
    if not normalized_names:
        return

    stmt = select(Ingredient).where(func.lower(Ingredient.name).in_(normalized_names))
    result = await db.execute(stmt)
    existing_ingredients = result.scalars().all()

    existing_map = {ing.name.lower(): ing for ing in existing_ingredients}
    to_create = normalized_names - set(existing_map.keys())

    new_ingredients = []
    for name in to_create:
        ing = Ingredient(name=name)
        new_ingredients.append(ing)
        db.add(ing)

    if new_ingredients:
        await db.flush()
        for ing in new_ingredients:
            existing_map[ing.name.lower()] = ing

    # Refresh the dish relationship to safely access the ingredients collection
    await db.refresh(dish, ["ingredients"])

    current_ingredient_names = {ing.name.lower() for ing in dish.ingredients}

    for name in normalized_names:
        if name not in current_ingredient_names:
            dish.ingredients.append(existing_map[name])
