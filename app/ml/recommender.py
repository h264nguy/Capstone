from __future__ import annotations

from collections import Counter, defaultdict
from math import sqrt
from typing import Dict, List, Tuple

from app.core.storage import load_orders, load_drinks


def _format_ing(ing: str) -> str:
    return str(ing).replace("_", " ").strip()

def _user_ing_counts(username: str, drink_by_id: Dict[str, dict]) -> Counter:
    orders = load_orders()
    c: Counter = Counter()
    for o in orders:
        if str(o.get("username")) != str(username):
            continue
        did = o.get("drinkId")
        if did is None:
            continue
        d = drink_by_id.get(str(did))
        if not d:
            continue
        ings = d.get("ingredients") if isinstance(d, dict) else None
        if not isinstance(ings, list):
            continue
        try:
            qty = int(o.get("quantity", 1))
        except Exception:
            qty = 1
        qty = max(1, qty)
        for ing in ings:
            if ing:
                c[str(ing)] += qty
    return c

def _attach_why(recs: List[dict], username: str, drink_by_id: Dict[str, dict], mood: str | None = None) -> List[dict]:
    counts = _user_ing_counts(username, drink_by_id)
    top_ings = [ing for ing, _ in counts.most_common(6)]
    out: List[dict] = []
    for d in recs:
        if not isinstance(d, dict):
            continue
        dd = dict(d)  # copy so we don't mutate global drink objects
        why: List[str] = []
        if mood:
            why.append(f"Matches mood: {mood}")
        ings = dd.get("ingredients")
        if isinstance(ings, list) and top_ings:
            common = [ing for ing in ings if str(ing) in set(top_ings)]
            # keep order, unique, max 3
            seen = set()
            picked = []
            for ing in common:
                s = str(ing)
                if s in seen:
                    continue
                seen.add(s)
                picked.append(_format_ing(s).title())
                if len(picked) >= 3:
                    break
            if picked:
                why.append("Shares: " + ", ".join(picked))
        if not why:
            why.append("Popular choice")
        dd["why"] = why
        out.append(dd)
    return out


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
        return _attach_why(out, username, drink_by_id, mood=None)

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


# -------------------------
# Mood-based logic
# -------------------------

MOOD_PROFILES: Dict[str, Dict[str, float]] = {
    # light/refreshing
    "chill": {
        "water": 1.0,
        "sprite": 0.8,
        "ginger_ale": 0.6,
        "lemonade": 0.6,
        "splash_of_water": 0.7,
        "splash_of_sprite": 0.7,
    },
    # higher energy / bold
    "energized": {
        "red_bull": 1.2,
        "coca_cola": 0.7,
        "sprite": 0.4,
        "ginger_ale": 0.4,
    },
    # fruity/sweeter
    "sweet": {
        "orange_juice": 1.0,
        "lemonade": 0.8,
        "sprite": 0.4,
        "coca_cola": 0.3,
    },
    # surprising mixes / complex
    "adventurous": {
        "ginger_ale": 0.9,
        "red_bull": 0.6,
        "coca_cola": 0.5,
        "orange_juice": 0.5,
        "sprite": 0.4,
    },
}

ALLOWED_MOODS = set(MOOD_PROFILES.keys())


def _mood_score(drink: dict, mood: str) -> float:
    """Score a drink by how well its ingredients match a mood profile."""
    profile = MOOD_PROFILES.get(mood, {})
    ings = drink.get("ingredients") or []
    if not isinstance(ings, list) or not profile:
        return 0.0
    s = 0.0
    for ing in ings:
        if ing in profile:
            s += float(profile[ing])
    # tiny bonus for more variety in adventurous
    if mood == "adventurous":
        s += 0.05 * max(0, len(ings) - 2)
    return s


def recommend_for_user_and_mood(username: str, mood: str, k: int = 5) -> List[dict]:
    """
    Hybrid recommender:
      - collaborative filtering baseline (recommend_for_user)
      - mood ingredient matching
      - user's past mood-specific ordering (if any)

    Returns list of drink dicts.
    """
    mood = (mood or "").strip().lower()
    if mood not in ALLOWED_MOODS:
        # fallback to baseline if mood unknown
        return recommend_for_user(username, k=k)

    drinks = load_drinks()
    drink_by_id = {str(d.get("id")): d for d in drinks if isinstance(d, dict) and d.get("id") is not None}

    # Candidate pool: take more than k from baseline, then re-rank by mood
    baseline = recommend_for_user(username, k=max(20, k * 6))
    candidate_ids = [str(d.get("id")) for d in baseline if d.get("id") is not None]

    # If baseline empty (shouldn't), fallback to all drinks
    if not candidate_ids:
        candidate_ids = [str(d.get("id")) for d in drinks if d.get("id") is not None]

    # User mood preference (implicit): what did they order *when they chose this mood*?
    orders = load_orders()
    mood_counts: Counter = Counter()
    for o in orders:
        if str(o.get("username")) != str(username):
            continue
        if str(o.get("mood") or "").strip().lower() != mood:
            continue
        did = o.get("drinkId")
        if did is None:
            continue
        try:
            qty = int(o.get("quantity", 1))
        except Exception:
            qty = 1
        mood_counts[str(did)] += max(1, qty)

    # Score + rank
    scored = []
    for idx, did in enumerate(candidate_ids):
        d = drink_by_id.get(str(did))
        if not d:
            continue

        ms = _mood_score(d, mood)  # 0..?
        # baseline rank -> higher score
        br = 1.0 / float(idx + 1)
        # mood history boost
        mh = float(mood_counts.get(str(did), 0))
        # dampen mh
        mh = (mh ** 0.5) / 3.0  # small, capped-ish

        score = (0.65 * ms) + (0.25 * br) + (0.10 * mh)
        scored.append((score, d))

    scored.sort(key=lambda x: x[0], reverse=True)
    out = [d for _, d in scored[:k]]
    return _attach_why(out, username, drink_by_id, mood=mood)
