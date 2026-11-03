"""Explicit downloads and offline validation of one pinned, local BGE model.

Git blob IDs / LFS SHA256 values are from the official Hugging Face revision API.
Only safetensors is downloaded; no pickle weights or remote Python modules.
"""

import hashlib
import json
import os
import tempfile
import urllib.request
from pathlib import Path

from knowledge_agent.errors import CorpusError
from knowledge_agent.retrieval.tokenizer import TOKENIZER_SPEC

MODEL_ID = TOKENIZER_SPEC["model"]
MODEL_REVISION = TOKENIZER_SPEC["revision"]
QUERY_INSTRUCTION = "为这个句子生成表示以用于检索相关文章："
DIMENSION = 512
MAX_TOKENS = 512
# name: (byte size, hash kind, expected hash); immutable remote identities.
MODEL_FILES = {
    "1_Pooling/config.json": (190, "git", "e25f4f3261cf0c6156611f5b5fdba0825859f4f3"),
    "README.md": (27670, "git", "20e39cd51a31d3afb1d003a9a4239f527530b1c0"),
    "config.json": (776, "git", "f79ec8dfc5812a1d5d7d2e69253eb9054be2246d"),
    "config_sentence_transformers.json": (124, "git", "dcb0c0d97d09b930d13600b1a773ddb27e441aab"),
    "model.safetensors": (95827648, "sha256", "354763b9b1357bc9c44f62c6be2276321081ed2567773608c0d0785b61d5a026"),
    "modules.json": (349, "git", "952a9b81c0bfd99800fabf352f69c7ccd46c5e43"),
    "sentence_bert_config.json": (52, "git", "ea85692bff64b0d1917833c31ddbca8ab10f5455"),
    "special_tokens_map.json": (125, "git", "a8b3208c2884c4efb86e49300fdd3dc877220cdf"),
    "tokenizer.json": (439125, "git", "cdb3043fc938fc918c06e66cf704c2ba58f88747"),
    "tokenizer_config.json": (367, "git", "3a59388f0fd1bd22dec2ce7902c1be8e1fb84107"),
    "vocab.txt": (109540, "git", "ca4f9781030019ab9b253c6dcb8c7878b6dc87a5"),
}


def verify_file(path: Path, spec: tuple) -> str:
    size, kind, expected = spec
    if not path.is_file() or path.stat().st_size != size:
        raise CorpusError("BGE 本地文件缺失或大小不符，请执行 download-model。")
    checksum = hashlib.sha256()
    identity = hashlib.sha1(f"blob {size}\0".encode()) if kind == "git" else hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            checksum.update(block)
            identity.update(block)
    if identity.hexdigest() != expected:
        raise CorpusError("BGE 本地文件与固定 revision 指纹不符，请重新 download-model。")
    return checksum.hexdigest()


def validate_model(path: Path) -> dict:
    """Hash actual bytes, not merely a self-reported local manifest. Never downloads."""
    hashes = {name: verify_file(path / name, spec) for name, spec in MODEL_FILES.items()}
    if hashes["tokenizer.json"] != TOKENIZER_SPEC["sha256"]:
        raise CorpusError("模型 tokenizer 与分块 tokenizer 不一致。")
    return {"model": MODEL_ID, "revision": MODEL_REVISION, "files_sha256": hashes}


def download_model(path: Path) -> dict:
    """Idempotent explicit preparation; interrupted files never replace valid assets."""
    for name, spec in MODEL_FILES.items():
        target = path / name
        try:
            verify_file(target, spec)
            continue
        except CorpusError:
            pass
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(prefix=".download-", dir=target.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(fd, "wb") as output:
                url = f"https://huggingface.co/{MODEL_ID}/resolve/{MODEL_REVISION}/{name}"
                with urllib.request.urlopen(url, timeout=30) as response:
                    received = 0
                    while block := response.read(1024 * 1024):
                        received += len(block)
                        if received > spec[0]:
                            raise CorpusError("BGE 下载超过固定文件大小，未保存。")
                        output.write(block)
            verify_file(temporary, spec)
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
    manifest = validate_model(path)
    # This is informative; runtime still independently validates all pinned files.
    (path / "model-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest
