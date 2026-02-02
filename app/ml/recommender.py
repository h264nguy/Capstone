from __future__ import annotations

from collections import Counter, defaultdict
from math import sqrt
from typing import Dict, List, Tuple

from app.core.storage import load_orders, load_drinks


def _cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
    """Cosine similarity of sparse vectors."""
    if not a or not b:
        return 0.0
    dot = 0.0
    for k, av in a.items():
        bv = b.get(k)
        if bv is not None:
            dot += av * bv
    na = sqrt(sum(v * v for v in a.values()))
    nb = sqrt(sum(v * v for v in b.values()))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _build_user_vectors() -> Tuple[Dict[str, Dict[str, float]], Counter]:
    """Returns (user->drinkId->count, global_drink_counts)."""
    orders = load_orders()
    user_vec: Dict[str, Counter] = defaultdict(Counter)
    global_counts: Counter = Counter()

    for o in orders:
        username = o.get("username")
        drink_id = o.get("drinkId")
        qty = o.get("quantity", 1)

        if not username or not drink_id:
            continue

        try:
            qty = int(qty)
        except Exception:
            qty = 1

        if qty < 1:
            qty = 1

        did = str(drink_id)
        user_vec[str(username)][did] += qty
        global_counts[did] += qty

    return ({u: dict(c) for u, c in user_vec.items()}, global_counts)


def recommend_for_user(username: str, k: int = 5) -> List[dict]:
    """
    Collaborative filtering-ish recommender.

    - If user has history: find similar users (cosine) and score drinks they like.
    - If not: return globally popular drinks.

    Returns list of drink dicts (id, name, calories).
    """
    drinks = load_drinks()
    drink_by_id = {
        str(d.get("id")): d
        for d in drinks
        if isinstance(d, dict) and d.get("id") is not None
    }

    user_vectors, global_counts = _build_user_vectors()
    target = user_vectors.get(str(username), {})

    def popular(exclude: set[str]) -> List[str]:
        return [did for did, _ in global_counts.most_common() if did not in exclude]

    tried = set(target.keys())

    # --- Cold start: no history for this user ---
    if not target:
        ids = popular(exclude=set()) if global_counts else [str(d.get("id")) for d in drinks if d.get("id") is not None]
        out: List[dict] = []
        for did in ids:
            d = drink_by_id.get(str(did))
            if d:
                out.append(d)
            if len(out) >= k:
                break
        return out

    # --- Find similar users ---
    sims: List[Tuple[str, float]] = []
    for other, vec in user_vectors.items():
        if other == str(username):
            continue
        s = _cosine(target, vec)
        if s > 0:
            sims.append((other, s))

    sims.sort(key=lambda x: x[1], reverse=True)
    sims = sims[:25]  # cap

    # --- Score candidate drinks from similar users ---
    scores: Counter = Counter()
    for other, s in sims:
        vec = user_vectors.get(other, {})
        for did, cnt in vec.items():
            if did in tried:
                continue
            scores[did] += s * float(cnt)

    ranked_ids = [did for did, _ in scores.most_common()]

    # If no similar-user signal, fallback to popularity excluding tried
    if not ranked_ids:
        ranked_ids = popular(exclude=tried)

    # Final fallback: any untried drinks from menu
    if not ranked_ids:
        ranked_ids = [str(d.get("id")) for d in drinks if d.get("id") is not None and str(d.get("id")) not in tried]

    out: List[dict] = []
    for did in ranked_ids:
        d = drink_by_id.get(str(did))
        if d:
            out.append(d)
        if len(out) >= k:
            break

    return out
