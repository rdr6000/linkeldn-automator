import pytest
from app.linkedin.ad_filter import is_ad_post, AD_KEYWORDS

def test_is_ad_post_detects_sponsored_keywords():
    ad_post_1 = {"text": "Check out our new AI platform!", "actor_subdescription": "Promoted by TechCorp"}
    ad_post_2 = {"text": "Sponsored content for developers", "actor_subdescription": "Software Lead"}
    ad_post_3 = {"text": "Amazing opportunities", "badge": "Paid partnership"}

    assert is_ad_post(ad_post_1) is True
    assert is_ad_post(ad_post_2) is True
    assert is_ad_post(ad_post_3) is True

def test_is_ad_post_allows_organic_posts():
    organic_post_1 = {"text": "Just launched an open source Python package!", "actor_subdescription": "Senior Engineer"}
    organic_post_2 = {"text": "Great article on software architecture", "actor_subdescription": "Tech Writer"}

    assert is_ad_post(organic_post_1) is False
    assert is_ad_post(organic_post_2) is False

def test_is_ad_post_handles_missing_fields_gracefully():
    assert is_ad_post({}) is False
    assert is_ad_post({"text": None, "actor_subdescription": None}) is False
