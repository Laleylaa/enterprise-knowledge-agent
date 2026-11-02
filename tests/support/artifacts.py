"""Export compact submission evidence; runtime debug files remain local."""

from pathlib import Path

import pytest

from knowledge_agent.artifact_export import export_run


@pytest.fixture
def archive_run(request):
    """Register run directories, exporting even failed runs at fixture teardown."""
    root = request.config.getoption("--examples-dir")
    destination = (request.config.invocation_params.dir / root).resolve() if root else None
    pending = []

    def register(scope: str, case_id: str, directory: Path):
        pending.append((scope, case_id, directory))

    yield register
    if destination is not None:
        for scope, case_id, directory in pending:
            if directory.is_dir():
                export_run(directory, destination / scope, case_id)
