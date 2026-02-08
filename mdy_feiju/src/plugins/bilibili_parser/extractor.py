import re
import httpx
from typing import Optional

# Regex to match BV IDs (BV1xx411c7mD)
# Case insensitive, usually starts with BV, followed by 10 alphanumeric chars
BV_PATTERN = re.compile(r'(BV[a-zA-Z0-9]{10})', re.IGNORECASE)

# Regex to match b23.tv short links
SHORT_LINK_PATTERN = re.compile(r'(https?://b23\.tv/[a-zA-Z0-9]+)', re.IGNORECASE)

async def extract_bv(text: str) -> Optional[str]:
    """
    Extract BV ID from text. 
    Handles:
    1. Direct BV ID in text.
    2. Long URL with BV ID.
    3. Short link (b23.tv) -> Resolve -> Extract BV ID.
    """
    if not text:
        return None

    # 1. Try to find short link first
    short_link_match = SHORT_LINK_PATTERN.search(text)
    if short_link_match:
        short_url = short_link_match.group(1)
        resolved_url = await _resolve_short_link(short_url)
        if resolved_url:
            # Recursively try to extract BV from the resolved URL
            # We don't recurse infinitely because resolved URL shouldn't be another b23.tv link usually
            # But to be safe, we just match BV pattern on the resolved URL
            bv_match = BV_PATTERN.search(resolved_url)
            if bv_match:
                return bv_match.group(1)

    # 2. Try to find BV ID directly in the text (or in the resolved URL from step 1 if we did it differently)
    # But since we returned early in step 1 if found, here we just look at the original text
    # This covers "Check this BV1xx..." or "https://www.bilibili.com/video/BV1xx..."
    bv_match = BV_PATTERN.search(text)
    if bv_match:
        return bv_match.group(1)

    return None

async def _resolve_short_link(url: str) -> Optional[str]:
    """
    Resolve b23.tv short link to long URL using HTTP HEAD/GET.
    """
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.head(url, timeout=5.0)
            # Sometimes HEAD might not work or return the final URL if it's a client-side split
            # But b23.tv usually redirects via 302
            
            # If HEAD doesn't give a 3xx/location, try GET (slower but more reliable for some shorteners)
            if resp.status_code == 200 and 'bilibili.com' not in str(resp.url):
                 resp = await client.get(url, timeout=5.0)

            return str(resp.url)
    except Exception as e:
        # Generate some logs if possible, or just return None
        print(f"Error resolving short link {url}: {e}")
        return None

def extract_from_json(json_data: dict) -> Optional[str]:
    """
    Extract relevant URL from JSON card data.
    Returns: URL string (BV link or short link) or None.
    """
    try:
        # Common Bilibili card structure in QQ
        # meta -> detail -> qqdocurl
        # meta -> news -> jumpUrl
        meta = json_data.get('meta', {})
        
        # Check standard Detail card
        detail = meta.get('detail_1') or meta.get('detail')
        if detail:
            # Look for explicit URL fields
            # qqdocurl usually contains the cleanest link for sharing
            url = detail.get('qqdocurl') or detail.get('preview') or detail.get('url')
            if url:
                # Validate it looks like a Bilibili link (BV or short link)
                if BV_PATTERN.search(url) or SHORT_LINK_PATTERN.search(url):
                    return url

        # Check News card
        news = meta.get('news')
        if news:
            url = news.get('jumpUrl') or news.get('action')
            if url:
                if BV_PATTERN.search(url) or SHORT_LINK_PATTERN.search(url):
                    return url
                    
        return None

    except Exception:
        return None
