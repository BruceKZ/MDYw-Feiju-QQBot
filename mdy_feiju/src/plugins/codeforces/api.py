import os
import json
import math
import asyncio
import httpx
from nonebot.log import logger
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone, timedelta
from pathlib import Path

# UTC+8 timezone
TZ_UTC8 = timezone(timedelta(hours=8))

# Rate limiting
REQUEST_INTERVAL_SEC = 2.2
REQUEST_TIMEOUT_SEC = 90
MAX_RETRIES = 5

# Disk cache for contest rating changes (survives restarts)
CACHE_DIR = Path(__file__).parent / "rating_cache"

# In-memory sorted rating list for percentile calculation
_rated_list: List[int] = []  # sorted descending
_rated_list_timestamp: Optional[datetime] = None
_total_active_users: int = 0


def get_cache_time() -> Optional[datetime]:
    """Returns the timestamp (UTC+8) of when the rating data was last updated."""
    return _rated_list_timestamp


async def _cf_get(client: httpx.AsyncClient, method: str, **params) -> Any:
    """Single CF API call."""
    url = f"https://codeforces.com/api/{method}"
    resp = await client.get(url, params=params, timeout=REQUEST_TIMEOUT_SEC)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "OK":
        raise RuntimeError(data.get("comment", "unknown error"))
    return data["result"]


async def _cf_get_with_retry(client: httpx.AsyncClient, method: str, **params) -> Any:
    """CF API call with retry + rate limiting."""
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = await _cf_get(client, method, **params)
            await asyncio.sleep(REQUEST_INTERVAL_SEC)
            return result
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                raise
            last_err = e
        except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.ConnectError) as e:
            last_err = e
        except Exception as e:
            last_err = e

        if attempt < MAX_RETRIES:
            wait_sec = min(30, 2 ** attempt)
            logger.warning(f"CF API retry {attempt}/{MAX_RETRIES}: {last_err} | sleep {wait_sec}s")
            await asyncio.sleep(wait_sec)

    raise last_err


def _load_cached_changes(contest_id: int) -> Optional[list]:
    """Load contest rating changes from disk cache."""
    path = CACHE_DIR / f"{contest_id}.json"
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_cached_changes(contest_id: int, changes: list) -> None:
    """Save contest rating changes to disk cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{contest_id}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(changes, f, ensure_ascii=False)


async def fetch_user_info(handle: str) -> Optional[Dict[str, Any]]:
    """Fetches CF user.info for a given handle."""
    try:
        async with httpx.AsyncClient() as client:
            result = await _cf_get_with_retry(client, "user.info", handles=handle)
            return result[0] if result else None
    except Exception as e:
        logger.error(f"Error fetching user info for {handle}: {e}")
        return None


async def update_cache() -> Optional[datetime]:
    """
    Rebuilds the active user rating list by scanning all rated contests
    from the last 6 months. Uses disk cache for individual contest data.
    Returns the timestamp (UTC+8) on success, None on failure.
    """
    global _rated_list, _rated_list_timestamp, _total_active_users

    try:
        async with httpx.AsyncClient() as client:
            # Step 1: Get recent finished contests
            logger.info("Step 1: Fetching contest list...")
            contests = await _cf_get_with_retry(client, "contest.list", gym="false")

            now_utc = datetime.now(timezone.utc)
            cutoff = now_utc - timedelta(days=183)

            recent = []
            for c in contests:
                start_ts = c.get("startTimeSeconds")
                if start_ts is None or c.get("phase") != "FINISHED":
                    continue
                start_dt = datetime.fromtimestamp(start_ts, tz=timezone.utc)
                duration_sec = c.get("durationSeconds", 0)
                end_dt = start_dt + timedelta(seconds=duration_sec)
                if end_dt >= cutoff:
                    recent.append(c)

            recent.sort(key=lambda x: x["startTimeSeconds"])
            logger.info(f"Found {len(recent)} finished contests in last ~6 months.")

            # Step 2: Collect rating changes per contest
            logger.info("Step 2: Collecting rating changes (with disk cache)...")
            latest_rating: Dict[str, int] = {}  # handle -> latest rating
            skipped = 0
            failed = 0

            for idx, contest in enumerate(recent, start=1):
                contest_id = int(contest["id"])
                contest_name = contest.get("name", "")

                # Try disk cache first
                changes = _load_cached_changes(contest_id)
                if changes is not None:
                    source = "cache"
                else:
                    try:
                        changes = await _cf_get_with_retry(
                            client, "contest.ratingChanges", contestId=contest_id
                        )
                        _save_cached_changes(contest_id, changes)
                        source = "API"
                    except httpx.HTTPStatusError as e:
                        if e.response.status_code == 400:
                            skipped += 1
                            continue
                        failed += 1
                        logger.warning(f"Failed contest {contest_id}: {e}")
                        continue
                    except Exception as e:
                        failed += 1
                        logger.warning(f"Failed contest {contest_id}: {e}")
                        continue

                # Update latest rating for each participant
                for ch in changes:
                    handle = ch["handle"]
                    ts = int(ch["ratingUpdateTimeSeconds"])
                    new_r = int(ch["newRating"])

                    if handle not in latest_rating:
                        latest_rating[handle] = (new_r, ts)
                    else:
                        _, prev_ts = latest_rating[handle]
                        if ts > prev_ts:
                            latest_rating[handle] = (new_r, ts)

                if idx % 20 == 0 or idx == len(recent):
                    logger.info(f"  Progress: {idx}/{len(recent)} contests processed, {len(latest_rating)} unique users so far.")

            # Step 3: Build sorted rating list
            ratings = [r for r, _ in latest_rating.values()]
            ratings.sort(reverse=True)

            _rated_list = ratings
            _total_active_users = len(ratings)
            _rated_list_timestamp = datetime.now(TZ_UTC8)

            logger.info(
                f"Rating cache updated: {_total_active_users} active users, "
                f"{skipped} skipped, {failed} failed. "
                f"Timestamp: {_rated_list_timestamp.strftime('%Y-%m-%d %H:%M:%S')} (UTC+8)"
            )
            return _rated_list_timestamp

    except Exception as e:
        logger.error(f"update_cache failed: {e}")
        return None


def get_percentile(rating: int) -> Optional[float]:
    """
    Returns the Top X.XX% for a given rating based on cached data.
    Purely local — never triggers a network fetch.
    """
    if not _rated_list:
        return None

    total = len(_rated_list)

    # Binary search for rank (list is sorted descending)
    # Find count of users with rating strictly greater
    lo, hi = 0, total
    while lo < hi:
        mid = (lo + hi) // 2
        if _rated_list[mid] > rating:
            lo = mid + 1
        else:
            hi = mid

    rank = lo + 1
    percent = (rank / total) * 100
    return percent
