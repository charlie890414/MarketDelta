import asyncio
import os

import pytest

from app.jobs.pipeline import run_fixture_pipeline


@pytest.mark.integration
def test_fixture_pipeline_is_idempotent_against_postgres():
    if os.getenv("MCE_INTEGRATION") != "1":
        pytest.skip("set MCE_INTEGRATION=1 to run database integration tests")

    first = asyncio.run(run_fixture_pipeline())
    second = asyncio.run(run_fixture_pipeline())

    assert first["status"] in {"success", "partial"}
    assert second["status"] in {"success", "partial"}
    assert second["snapshots_inserted"] == 0
    assert second["changes_detected"] == 0
