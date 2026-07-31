from typing import Dict, Any

AD_KEYWORDS = [
    "promoted", "sponsored", "promoted by", "sponsored by",
    "paid partnership", "ad ", "• promoted"
]


def is_ad_post(post: Dict[str, Any]) -> bool:
    """
    Pure Python filter to detect sponsored or advertised LinkedIn posts based on content
    and author subdescription text.
    """
    if not isinstance(post, dict):
        return False

    text_parts = [
        str(post.get("text") or ""),
        str(post.get("actor_subdescription") or ""),
        str(post.get("subdescription") or ""),
        str(post.get("badge") or ""),
        str(post.get("header") or ""),
    ]
    combined_text = " ".join(text_parts).lower()

    return any(keyword in combined_text for keyword in AD_KEYWORDS)
