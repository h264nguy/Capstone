from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.auth import current_user
from app.ml.recommender import recommend_for_user

router = APIRouter()


@router.get("/api/recommendations")
def api_recommendations(request: Request, k: int = 5):
    user = current_user(request)
    if not user:
        return JSONResponse({"ok": False, "error": "Not logged in"}, status_code=401)

    recs = recommend_for_user(user, k=max(1, min(int(k), 20)))
    return JSONResponse({"ok": True, "username": user, "recommendations": recs})
