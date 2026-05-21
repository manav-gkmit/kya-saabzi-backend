from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.dishes import Dish, Ingredient


def attach_ingredients_to_dish(db: Session, dish: Dish, ingredient_names: list[str]) -> None:
    """Find or create ingredients by name and attach them to the given dish."""
    normalized_names = {name.lower().strip() for name in ingredient_names if name.strip()}
    if not normalized_names:
        return

    existing_ingredients = (
        db.query(Ingredient).filter(func.lower(Ingredient.name).in_(normalized_names)).all()
    )

    existing_map = {ing.name.lower(): ing for ing in existing_ingredients}
    to_create = normalized_names - set(existing_map.keys())

    new_ingredients = []
    for name in to_create:
        ing = Ingredient(name=name)
        new_ingredients.append(ing)
        db.add(ing)

    if new_ingredients:
        db.flush()
        for ing in new_ingredients:
            existing_map[ing.name.lower()] = ing

    current_ingredient_names = {ing.name.lower() for ing in dish.ingredients}

    for name in normalized_names:
        if name not in current_ingredient_names:
            dish.ingredients.append(existing_map[name])


async def attach_ingredients_to_dish_async(
    db: AsyncSession, dish: Dish, ingredient_names: list[str]
) -> None:
    """Find or create ingredients by name and attach them to the given dish asynchronously."""
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

