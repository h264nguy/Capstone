from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.auth import current_user

# -------------------------
# Ingredient labels (normalized id -> display)
# -------------------------
INGREDIENT_LABELS = {
  "coca_cola": "Coca-Cola",
  "red_bull": "Red Bull",
  "ginger_ale": "Ginger Ale",
  "orange_juice": "Orange Juice",
  "sprite": "Sprite",
  "water": "Water",
  "lemonade": "Lemonade",
  "splash_of_water": "Splash of Water",
  "splash_of_sprite": "Splash of Sprite",
}

def pretty_ingredient(ing: str) -> str:
    if not ing:
        return ""
    return INGREDIENT_LABELS.get(ing, ing.replace("_"," ").title())
from app.ml.recommender import recommend_for_user

router = APIRouter()


@router.get("/api/recommendations")
def api_recommendations(request: Request, k: int = 5):
    user = current_user(request)
    if not user:
        return JSONResponse({"ok": False, "error": "Not logged in"}, status_code=401)

    recs = recommend_for_user(user, k=max(1, min(int(k), 20)))
    return JSONResponse({"ok": True, "username": user, "recommendations": recs})
