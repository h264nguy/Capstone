from __future__ import annotations

from collections import Counter, defaultdict
from math import sqrt
from typing import Dict, List, Tuple

from app.core.storage import load_orders, load_drinks


def _cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
    # cosine similarity of sparse vectors
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
        user_vec[username][str(drink_id)] += qty
        global_counts[str(drink_id)] += qty

    # convert Counter -> dict[str,float]
    return ({u: dict(c) for u, c in user_vec.items()}, global_counts)


def recommend_for_user(username: str, k: int = 5) -> List[dict]:
    """Collaborative-filtering-ish recommender.

    - If user has history: find similar users (cosine) and score drinks they like.
    - If not: return globally popular drinks.

    Returns list of drink dicts (id, name, calories).
    """
    drinks = load_drinks()
    drink_by_id = {d.get("id"): d for d in drinks if isinstance(d, dict) and d.get("id")}

    user_vectors, global_counts = _build_user_vectors()
    target = user_vectors.get(username, {})

    # fallback: popular drinks
    def popular(exclude: set[str]) -> List[str]:
        return [did for did, _ in global_counts.most_common() if did not in exclude]

    tried = set(target.keys())

    if not target:
        # If we have no global counts yet, just return the menu top k.
        if not global_counts:
            ids = [d.get("id") for d in drinks if d.get("id")]
        else:
            ids = popular(exclude=set())
        out = []
        for did in ids:
            if did in drink_by_id:
                out.append(drink_by_id[did])
            if len(out) >= k:
                break
        return out

    # compute similarity with others
    sims: List[Tuple[str, float]] = []
    for other, vec in user_vectors.items():
        if other == username:
            continue
        s = _cosine(target, vec)
        if s > 0:
            sims.append((other, s))

    sims.sort(key=lambda x: x[1], reverse=True)
    sims = sims[:25]  # cap

    # score drinks based on similar users
    scores: Counter = Counter()
    for other, s in sims:
        vec = user_vectors.get(other, {})
        for did, cnt in vec.items():
            if did in tried:
                continue
            scores[did] += s * float(cnt)

    # if nothing scored (no similar users), back off to popularity excluding tried
    ranked_ids = [did for did, _ in scores.most_common()]
    if not ranked_ids:
        ranked_ids = popular(exclude=tried)

    # Final fallback: suggest any drinks you haven't tried yet (even if they have 0 orders)
    if not ranked_ids:
        ranked_ids = [d.get("id") for d in drinks if d.get("id") and d.get("id") not in tried]
    out = []
    for did in ranked_ids:
        d = drink_by_id.get(did)
        if d:
            out.append(d)
        if len(out) >= k:
            break

    return out
