"""Pinned BGE tokenizer. Network is used only by the explicit download command."""

import hashlib
from importlib.metadata import version
from pathlib import Path

from tokenizers import Tokenizer

from knowledge_agent.errors import CorpusError

TOKENIZER_SPEC = {
    "model": "BAAI/bge-small-zh-v1.5",
    "revision": "7999e1d3359715c523056ef9478215996d62a620",
    "sha256": "48cea5d44424912a6fd1ea647bf4fe50b55ab8b1e5879c3275f80e339e8fae26",
    "library": "tokenizers", "library_version": "0.22.1",
}


class BgeTokenizer:
    def __init__(self, path: Path):
        if version("tokenizers") != TOKENIZER_SPEC["library_version"]:
            raise CorpusError("tokenizers 依赖版本与分块契约不符，请按 requirements.txt 安装。")
        if not path.is_file():
            raise CorpusError("缺少本地 BGE tokenizer；请先执行 download-tokenizer，再执行 prepare。")
        if hashlib.sha256(path.read_bytes()).hexdigest() != TOKENIZER_SPEC["sha256"]:
            raise CorpusError("tokenizer 文件与固定版本指纹不符。")
        self._tokenizer = Tokenizer.from_file(str(path))
        self._tokenizer.no_truncation()
        self._tokenizer.no_padding()

    def count(self, text: str) -> int:
        return len(self._tokenizer.encode(text, add_special_tokens=True).ids)

    def offsets(self, text: str) -> list[tuple[int, int]]:
        return self._tokenizer.encode(text, add_special_tokens=False).offsets


def download_tokenizer(path: Path) -> None:
    import urllib.request

    spec = TOKENIZER_SPEC
    url = f"https://huggingface.co/{spec['model']}/resolve/{spec['revision']}/tokenizer.json"
    with urllib.request.urlopen(url, timeout=30) as response:
        raw = response.read()
    if hashlib.sha256(raw).hexdigest() != spec["sha256"]:
        raise CorpusError("下载的 tokenizer 指纹不符，未保存。")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_bytes(raw)
    temporary.replace(path)
