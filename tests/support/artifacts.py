"""Export actual test runs without changing the runtime's recording format."""

import hashlib
import json
import shutil
from pathlib import Path

import pytest


def artifact_group(name: str) -> str:
    if name in {"input.json", "corpus.json", "index-manifest.json", "fault-injection.json"}:
        return "inputs"
    if name in {"output.json", "run-summary.json"}:
        return "outputs"
    if name in {"retrieval-evaluation.json", "reading-evaluation.json"}:
        return "reports"
    return "traces"


def export_run(source: Path, destination: Path, case_id: str) -> dict:
    """Copy a completed or interrupted run; reject collisions, preserve raw bytes."""
    run_id = source.name
    for value in (case_id, run_id):
        if not value or value in {".", ".."} or Path(value).name != value:
            raise ValueError("case_id and run_id must be single path components")
    files = sorted(path for path in source.iterdir() if path.is_file())
    entries = []
    for path in files:
        target = destination / artifact_group(path.name) / case_id / run_id / path.name
        if target.exists() and target.read_bytes() != path.read_bytes():
            raise FileExistsError(f"Refusing to overwrite a different artifact: {target}")
        entries.append((path, target, hashlib.sha256(path.read_bytes()).hexdigest()))
    manifest = {"case_id": case_id, "run_id": run_id, "artifacts": [
        {"path": target.relative_to(destination).as_posix(), "sha256": checksum}
        for _, target, checksum in entries
    ]}
    manifest_path = destination / "traces" / case_id / run_id / "artifacts.json"
    encoded = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    if manifest_path.exists() and manifest_path.read_text(encoding="utf-8") != encoded:
        raise FileExistsError(f"Refusing to overwrite a different manifest: {manifest_path}")
    for path, target, checksum in entries:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        assert hashlib.sha256(target.read_bytes()).hexdigest() == checksum
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(encoded, encoding="utf-8")
    return manifest


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
