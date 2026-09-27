"""
Contract tests for the complaints endpoints (§2.2). Fill these in as you
implement app/routes/complaints.py — each corresponds directly to a rubric
line item in section C.
"""
import pytest


@pytest.mark.anyio
async def test_create_complaint_returns_201(client):
    # TODO(you): POST a valid payload, assert 201 and response shape matches ComplaintOut
    raise NotImplementedError


@pytest.mark.anyio
async def test_create_complaint_rejects_short_text(client):
    # TODO(you): text < 10 chars -> 400 with field-level error body
    raise NotImplementedError


@pytest.mark.anyio
async def test_get_complaint_404_when_missing(client):
    # TODO(you): GET a random UUID -> 404
    raise NotImplementedError


@pytest.mark.anyio
async def test_list_complaints_paginates_and_filters(client):
    # TODO(you): seed a few complaints, assert page/page_size/total behave,
    # and that category/priority/status filters actually narrow results
    raise NotImplementedError


@pytest.mark.anyio
async def test_list_complaints_clamps_page_size_to_100(client):
    # TODO(you): request page_size=500, assert the effective page_size is <=100
    raise NotImplementedError


@pytest.mark.anyio
async def test_status_transition_open_to_in_progress_succeeds(client):
    raise NotImplementedError


@pytest.mark.anyio
async def test_invalid_status_transition_returns_409_naming_transition(client):
    # TODO(you): e.g. resolved -> open should 409, and the body must NAME the
    # attempted transition (§2.2), not just say "error"
    raise NotImplementedError


@pytest.mark.anyio
async def test_rate_limit_exceeded_returns_429_with_retry_after(client):
    # TODO(you): hammer POST /api/complaints past the configured limit,
    # assert 429 and a Retry-After header is present
    raise NotImplementedError


@pytest.mark.anyio
async def test_stats_cache_hit_then_miss_headers(client):
    # TODO(you): first request after invalidation -> X-Cache: MISS,
    # second request within TTL -> X-Cache: HIT
    raise NotImplementedError
