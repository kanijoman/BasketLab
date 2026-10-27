"""The API server used by the web smoke e2e (issue #111) must keep working: real app on mongomock (fixture `smoke_api` of conftest)."""


def test_seeded_competition_is_listed_and_the_internal_collection_is_not(smoke_api):
    http, name = smoke_api
    names = [c["name"] for c in http.get("/api/v1/collections/list").json()]
    assert names == [name]


def test_pages_of_the_smoke_have_data(smoke_api):
    http, name = smoke_api
    assert http.get("/api/v1/health/db").json()["connected"] is True
    assert http.get(f"/api/v1/teams/{name}").json()["team_stats"]
    assert len(http.get(f"/api/v1/possessions/{name}").json()) >= 2
