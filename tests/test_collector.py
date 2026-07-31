import pytest
from app.services.collector import normalize_feed, normalize_people, dedup_by_url, extract_target_label

def test_normalize_feed():
    raw_feed = [
        {"url": "https://linkedin.com/posts/1", "author": "Alice", "text": "Post 1 text", "actor_subdescription": "Software Lead"},
        {"link": "https://linkedin.com/posts/2", "name": "Bob", "content": "Post 2 text"}
    ]
    normalized = normalize_feed(raw_feed)
    assert len(normalized) == 2
    assert normalized[0]["url"] == "https://linkedin.com/posts/1"
    assert normalized[0]["author"] == "Alice"
    assert normalized[1]["url"] == "https://linkedin.com/posts/2"
    assert normalized[1]["author"] == "Bob"

def test_extract_target_label_from_url_slug():
    name_1 = extract_target_label("https://www.linkedin.com/posts/komal-bajaj-b23575212_post", "Post text")
    assert name_1 == "Komal Bajaj"

    name_2 = extract_target_label("https://www.linkedin.com/posts/aviral-singh-991823", "Post text")
    assert name_2 == "Aviral Singh"

    name_profile = extract_target_label("https://www.linkedin.com/in/jayraj-raulji-bb1808276/", "")
    assert name_profile == "Jayraj Raulji Bb1808276"

def test_normalize_people():
    raw_people = [
        {"profile_url": "https://linkedin.com/in/john", "name": "John Doe", "headline": "AI Researcher"},
        {"link": "https://linkedin.com/in/jane", "title": "Jane Smith", "occupation": "Data Scientist"}
    ]
    normalized = normalize_people(raw_people)
    assert len(normalized) == 2
    assert normalized[0]["url"] == "https://linkedin.com/in/john"
    assert normalized[0]["name"] == "John Doe"
    assert normalized[1]["url"] == "https://linkedin.com/in/jane"
    assert normalized[1]["name"] == "Jane Smith"

def test_dedup_by_url():
    items = [
        {"url": "https://linkedin.com/posts/1", "id": 1},
        {"url": "https://LINKEDIN.com/posts/1", "id": 2},
        {"url": "https://linkedin.com/posts/2", "id": 3}
    ]
    unique = dedup_by_url(items)
    assert len(unique) == 2
    assert unique[0]["id"] == 1
    assert unique[1]["id"] == 3
