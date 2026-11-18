"""End to end: index documents, search, evaluate, serve through the API. Requires pgvector."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from ictkb.chunking import chunk_markdown
from ictkb.embedding import HashEmbedder
from ictkb.indexer import IndexDoc, reindex_all, run_index
from ictkb.keys import create_key
from ictkb.search import Filters, search

pytestmark = pytest.mark.integration


def mk(doc_id, category, title, body, status="verified", tier="semester", days_old=0, level=("all",), **extra):
    meta = {
        "id": doc_id, "title": title, "category": category, "source_type": "official_doc",
        "freshness_tier": tier, "status": status,
        "last_verified": (date.today() - timedelta(days=days_old)).isoformat(),
        "owner": "handle", "program_level": list(level), "attachments": [], "tags": [], "related": [],
        "language": "en", **extra,
    }
    return IndexDoc(id=doc_id, meta=meta, chunks=chunk_markdown(title, body))


DOCS = [
    mk("finance-installments", "finance", "Paying tuition in installments",
       "## Can I pay in installments?\n\nYes. Tuition may be paid in three installments: 50 percent at registration, 30 percent in month two and 20 percent in month three."),
    mk("canteen-hours", "canteen", "Canteen opening hours",
       "## Opening times\n\nThe canteen opens at 7:30 and closes at 18:00 from Monday to Saturday."),
    mk("erp-first-login", "erp", "First login to the ERP",
       "## First login steps\n\nOpen the ERP address, enter your matricule as username and change the temporary password."),
    mk("about-draft-note", "about", "Draft note", "This is a draft note about nothing important at all.", status="draft"),
]


def test_index_search_filters_and_pruning(conn):
    emb = HashEmbedder()
    report = run_index(conn, emb, DOCS, origin="git", statuses=["verified"])
    assert (report.inserted, report.skipped) == (3, 1)

    out = search(conn, emb, "how to pay fees in installments", 3)
    assert out.results[0]["document"]["id"] == "finance-installments"
    assert out.confidence == "high"
    assert search(conn, emb, "canteen opens", 3, Filters(category="canteen")).results[0]["document"]["id"] == "canteen-hours"
    assert search(conn, emb, "pay installments", 3, Filters(category="erp")).results[0]["document"]["id"] == "erp-first-login"
    assert all(r["document"]["status"] == "verified" for r in search(conn, emb, "draft note", 5).results)

    # unchanged content is not re-embedded; removing a document prunes it
    again = run_index(conn, emb, DOCS[:2], origin="git", statuses=["verified"])
    assert (again.unchanged, again.deleted) == (2, 1)
    assert conn.execute("SELECT count(*) AS n FROM documents").fetchone()["n"] == 2


def test_embedding_model_guard_and_reindex(conn):
    emb = HashEmbedder()
    run_index(conn, emb, DOCS[:1], origin="git", statuses=["verified"])

    class Other(HashEmbedder):
        name = "other:v2"

    with pytest.raises(RuntimeError, match="reindex"):
        run_index(conn, Other(), DOCS[:1], origin="git", statuses=["verified"])
    conn.rollback()
    assert reindex_all(conn, Other()) >= 1
    run_index(conn, Other(), DOCS[:1], origin="git", statuses=["verified"])


def test_no_answer_is_low_confidence(conn):
    emb = HashEmbedder()
    run_index(conn, emb, DOCS, origin="git", statuses=["verified"])
    out = search(conn, emb, "zebra quantum volleyball tournament", 3)
    assert out.confidence in ("low", "none")


def test_sheet_sync_from_local_csv(conn, tmp_path):
    from ictkb.connectors import sheets

    csv_path = tmp_path / "menu.csv"
    csv_path.write_text("Day,Meal,Item,Price XAF,Available,Notes\nMonday,Lunch,Rice and beans,500,Yes,\nMonday,Lunch,Fried plantain,300,Yes,\n", encoding="utf-8")
    cfg = {**next(c for c in sheets.load_config() if c["name"] == "canteen-menu"), "csv_path": str(csv_path)}
    emb = HashEmbedder()
    # csv_path is resolved against the repository root; an absolute path replaces it
    report = sheets.sync_sheet(conn, emb, cfg)
    assert report.inserted == 1
    out = search(conn, emb, "price of rice and beans", 3)
    assert "Rice and beans" in out.results[0]["text"] and out.results[0]["document"]["id"] == "canteen-menu"
    # unchanged sync keeps last_verified; a changed sheet bumps content
    assert sheets.sync_sheet(conn, emb, cfg).unchanged == 1
    # an empty sheet must not wipe the index
    csv_path.write_text("Day,Meal,Item,Price XAF,Available,Notes\n", encoding="utf-8")
    with pytest.raises(RuntimeError):
        sheets.sync_sheet(conn, emb, cfg)
    assert conn.execute("SELECT count(*) AS n FROM documents").fetchone()["n"] == 1


def test_api_auth_search_feedback_rate_limit(conn):
    from fastapi.testclient import TestClient

    from ictkb.api import deps
    from ictkb.api.main import create_app

    emb = HashEmbedder()
    run_index(conn, emb, DOCS, origin="git", statuses=["verified"])
    key_id, key = create_key(conn, "tester", rate_limit_per_min=5)
    deps.clear_key_cache()
    deps._hits.clear()

    with TestClient(create_app()) as client:
        assert client.get("/v1/health").json()["documents"] == 3
        assert client.post("/v1/search", json={"query": "installments"}).status_code == 401
        assert client.post("/v1/search", json={"query": "installments"}, headers={"X-API-Key": "bad"}).status_code == 401
        h = {"X-API-Key": key}
        r = client.post("/v1/search", json={"query": "pay fees in installments", "top_k": 2}, headers=h)
        body = r.json()
        assert r.status_code == 200 and body["results"][0]["document"]["id"] == "finance-installments"
        assert body["results"][0]["document"]["stale"] is False
        assert client.get("/v1/documents/canteen-hours", headers=h).json()["chunks"]
        assert client.get("/v1/documents/about-draft-note", headers=h).status_code == 404  # drafts were not indexed
        assert client.post("/v1/feedback", json={"query": "q", "verdict": "wrong"}, headers=h).status_code == 201
        assert client.get("/v1/documents/nope", headers=h).status_code == 404  # 5th request in the window
        assert client.get("/v1/categories", headers=h).status_code == 429

        # admin surface
        assert client.post("/v1/admin/keys", json={"owner": "x"}).status_code == 403
        made = client.post("/v1/admin/keys", json={"owner": "student-one"}, headers={"X-Admin-Token": "test-admin-token"})
        assert made.status_code == 201
        assert client.delete(f"/v1/admin/keys/{key_id}", headers={"X-Admin-Token": "test-admin-token"}).status_code == 200
        assert client.post("/v1/search", json={"query": "installments"}, headers=h).status_code == 401


def test_evaluation_reports_coverage(conn):
    from ictkb.evaluation import evaluate, passes

    emb = HashEmbedder()
    run_index(conn, emb, DOCS, origin="git", statuses=["verified"])
    questions = [
        {"id": "A", "question": "Can I pay my fees in installments?", "type": "factual", "priority": "P0", "expected_docs": ["finance-installments"]},
        {"id": "B", "question": "How do I request a transcript?", "type": "procedural", "priority": "P0", "expected_docs": ["procedures-transcript"]},
        {"id": "C", "question": "What time does the canteen open?", "type": "factual", "priority": "P1", "expected_docs": ["canteen-hours"]},
        {"id": "N", "question": "zebra quantum volleyball tournament", "type": "no-answer", "priority": "P2", "expected_docs": []},
    ]
    result = evaluate(conn, emb, questions)
    s = result["summary"]
    assert s["covered"] == 2 and s["answerable"] == 3 and s["hit_at_k"] == 1.0
    assert passes(s, strict=False)[0] and not passes(s, strict=True)[0]


def test_notes_post_expire_and_reject_private_email(conn):
    from datetime import timedelta

    from ictkb.notes import post_note, prune_expired

    emb = HashEmbedder()
    today_ = date.today()
    doc_id = post_note(conn, emb, "canteen-menu", "Rice and beans 500 FCFA, fried plantain 300 FCFA", "tester")
    assert doc_id == f"canteen-menu-{today_.isoformat()}"
    out = search(conn, emb, "rice and beans price", 3)
    assert out.results[0]["document"]["id"] == doc_id
    # posting again for the same day replaces the earlier post
    post_note(conn, emb, "canteen-menu", "Jollof rice 600 FCFA", "tester")
    assert conn.execute("SELECT count(*) AS n FROM documents WHERE origin = 'note'").fetchone()["n"] == 1
    old = post_note(conn, emb, "announcement", "Classes resume Monday", "tester", on=today_ - timedelta(days=30), title="Resumption")
    assert prune_expired(conn) == 1
    assert conn.execute("SELECT count(*) AS n FROM documents WHERE id = %s", (old,)).fetchone()["n"] == 0
    with pytest.raises(ValueError):
        post_note(conn, emb, "announcement", "Write to someone@gmail.com now", "tester")


def test_notes_key_delete_and_transcribe_endpoints(conn, monkeypatch):
    from fastapi.testclient import TestClient

    from ictkb.api.main import create_app
    from ictkb.notes import post_note

    emb = HashEmbedder()
    a = post_note(conn, emb, "announcement", "Classes resume", "tester", title="Notice", key="notice-aaaaaa")
    b = post_note(conn, emb, "announcement", "Exam hall changed", "tester", title="Notice", key="notice-bbbbbb")
    assert a != b  # two messages with the same first line do not overwrite each other
    c = post_note(conn, emb, "student-life-post", "Football trials on Saturday", "tester", title="Trials")
    assert c.startswith("student-life-update-")

    admin = {"X-Admin-Token": "test-admin-token"}
    monkeypatch.setattr("ictkb.vision.transcribe_image", lambda data, mime, kind: "Rice 500 FCFA" if data == b"img" else "")
    with TestClient(create_app()) as client:
        import base64

        good = client.post("/v1/admin/transcribe", json={"image_base64": base64.b64encode(b"img" * 10).decode()}, headers=admin)
        assert good.status_code == 200
        bad = client.post("/v1/admin/transcribe", json={"image_base64": "not base64 !!!!!!!!!!!!"}, headers=admin)
        assert bad.status_code == 422
        assert client.post("/v1/admin/transcribe", json={"image_base64": "aaaaaaaaaaaaaaaaaaaaaaaa"}).status_code == 403
        assert client.delete(f"/v1/admin/notes/{a}", headers=admin).status_code == 200
        assert client.delete(f"/v1/admin/notes/{a}", headers=admin).status_code == 404
        # only posts can be deleted through this route
        run_index(conn, emb, DOCS[:1], origin="git", statuses=["verified"])
        assert client.delete("/v1/admin/notes/finance-installments", headers=admin).status_code == 404
