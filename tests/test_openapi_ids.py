"""The OpenAPI schema must not contain duplicate operation IDs."""

import warnings
from collections import Counter

from fastapi.testclient import TestClient

from src.main import app


def _build_schema():
    app.openapi_schema = None
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        schema = app.openapi()
    return schema, caught


def test_no_duplicate_operation_id_warnings():
    _, caught = _build_schema()
    dups = [str(w.message) for w in caught if "Duplicate Operation ID" in str(w.message)]
    assert dups == []


def test_operation_ids_are_unique():
    schema, _ = _build_schema()
    ids = [
        op["operationId"]
        for ops in schema["paths"].values()
        for op in ops.values()
        if isinstance(op, dict) and "operationId" in op
    ]
    repeated = [k for k, v in Counter(ids).items() if v > 1]
    assert repeated == []


def test_head_on_health_probes_still_works():
    client = TestClient(app)
    assert client.head("/health/live").status_code == 200
    assert client.head("/api/health/live").status_code == 200
