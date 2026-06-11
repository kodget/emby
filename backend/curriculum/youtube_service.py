"""
YouTube Data API v3 integration (PRD §6.3.5).

Turns a search query into real, educational YouTube results: title, channel,
duration, thumbnail and a watchable link. Degrades gracefully — if no
YOUTUBE_API_KEY is configured or the API errors, callers fall back to
AI-suggested search queries.
"""

import logging
import re
from typing import List, Dict, Optional

import requests

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"


def _get_api_key() -> str:
    try:
        from django.conf import settings
        return getattr(settings, "YOUTUBE_API_KEY", "") or ""
    except Exception:
        import os
        return os.getenv("YOUTUBE_API_KEY", "")


def is_configured() -> bool:
    return bool(_get_api_key())


def _parse_iso8601_duration(iso: str) -> str:
    """Convert e.g. 'PT1H2M30S' -> '1:02:30', 'PT4M5S' -> '4:05'."""
    if not iso:
        return ""
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso)
    if not match:
        return ""
    hours, minutes, seconds = (int(x) if x else 0 for x in match.groups())
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def search_videos(query: str, max_results: int = 5) -> Optional[List[Dict]]:
    """
    Search YouTube for educational videos matching the query.

    Returns a list of dicts (title, channel, video_id, url, thumbnail, duration)
    or None when YouTube is not configured / unavailable so the caller can fall back.
    """
    api_key = _get_api_key()
    if not api_key:
        return None
    if not query or not query.strip():
        return []

    try:
        search_resp = requests.get(
            SEARCH_URL,
            params={
                "key": api_key,
                "q": query,
                "part": "snippet",
                "type": "video",
                "maxResults": max_results,
                "videoEmbeddable": "true",
                "safeSearch": "strict",
                "relevanceLanguage": "en",
                # category 27 = "Education"
                "videoCategoryId": "27",
            },
            timeout=10,
        )
        search_resp.raise_for_status()
        items = search_resp.json().get("items", [])
        video_ids = [it["id"]["videoId"] for it in items if it.get("id", {}).get("videoId")]

        durations = {}
        if video_ids:
            details = requests.get(
                VIDEOS_URL,
                params={
                    "key": api_key,
                    "id": ",".join(video_ids),
                    "part": "contentDetails",
                },
                timeout=10,
            )
            if details.ok:
                for d in details.json().get("items", []):
                    durations[d["id"]] = _parse_iso8601_duration(
                        d.get("contentDetails", {}).get("duration", "")
                    )

        results = []
        for it in items:
            vid = it.get("id", {}).get("videoId")
            if not vid:
                continue
            snippet = it.get("snippet", {})
            thumbs = snippet.get("thumbnails", {})
            thumb = (thumbs.get("medium") or thumbs.get("default") or {}).get("url", "")
            results.append({
                "title": snippet.get("title", ""),
                "channel": snippet.get("channelTitle", ""),
                "video_id": vid,
                "url": f"https://www.youtube.com/watch?v={vid}",
                "thumbnail": thumb,
                "duration": durations.get(vid, ""),
            })
        return results

    except requests.HTTPError as e:
        logger.error(f"YouTube API HTTP error for '{query}': {e} — {getattr(e.response, 'text', '')[:200]}")
        return None
    except Exception as e:
        logger.error(f"YouTube search error for '{query}': {e}")
        return None
