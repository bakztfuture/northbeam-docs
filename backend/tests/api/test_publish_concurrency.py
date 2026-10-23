"""Simultaneous writes to one article run one after the other (EC-04, EC-33).

Each thread calls the publishing service on its own connection, released together by a barrier.
"""

import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

from app.models import PublishArticleRequest
from app.repositories.database import connect
from app.services import publishing

from ..helpers import create_article, get_article, publish


def run_together(settings, *calls):
    """Run each call(conn) in its own thread at the same moment; return their results in order."""
    barrier = threading.Barrier(len(calls))
    # A long busy timeout, so the second writer waits for the lock instead of getting a 503.
    patient = replace(settings, busy_timeout_ms=5000)

    def run(call):
        conn = connect(patient)
        try:
            barrier.wait()
            return call(conn)
        finally:
            conn.close()

    with ThreadPoolExecutor(len(calls)) as pool:
        return [future.result() for future in [pool.submit(run, call) for call in calls]]


def test_two_publishes_get_consecutive_numbers(client, settings):  # EC-04
    article = create_article(client)
    request = PublishArticleRequest(expected_draft_version=1)

    results = run_together(
        settings,
        lambda conn: publishing.publish_article(conn, article["id"], request),
        lambda conn: publishing.publish_article(conn, article["id"], request),
    )

    numbers = sorted(snapshot["version_number"] for _, snapshot in results)
    assert numbers == [1, 2]
    highest = max((snapshot for _, snapshot in results), key=lambda snapshot: snapshot["version_number"])
    assert get_article(client, article["id"])["currentPublishedVersionId"] == highest["id"]


def test_publish_and_unpublish_together_leave_a_consistent_row(client, settings):  # EC-33
    first = publish(client, create_article(client))["article"]

    (_, snapshot), _ = run_together(
        settings,
        lambda conn: publishing.publish_article(conn, first["id"], PublishArticleRequest(expected_draft_version=1)),
        lambda conn: publishing.unpublish_article(conn, first["id"]),
    )

    after = get_article(client, first["id"])
    assert after["status"] in ("published", "unpublished")
    assert after["currentPublishedVersionId"] == snapshot["id"]
    assert after["publishedAt"] == first["publishedAt"]
