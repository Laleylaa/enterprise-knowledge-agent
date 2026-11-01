"""A reusable spawned CPU worker with a kill-and-reap cancellation boundary.

IPC carries tiny control messages only. Arrays/text travel through a private temporary
directory, so a large pipe send/recv cannot block the parent's deadline handling.
The synchronous facade is for standalone callers; async callers use aencode/astart.
"""

import asyncio
import json
import multiprocessing
import os
import signal
import tempfile
import threading
import time
from pathlib import Path

import numpy as np

from knowledge_agent.config import Settings
from knowledge_agent.retrieval.failures import RetrievalFailure
from knowledge_agent.retrieval.model_assets import DIMENSION, MAX_TOKENS, validate_model


def run_embedding_worker(connection, directory: str, config: dict) -> None:
    """Production child target; imports neural dependencies only inside this process."""
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    for name in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_HUB_DISABLE_TELEMETRY"):
        os.environ[name] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
    for name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        os.environ[name] = str(config["threads"])
    root = Path(directory)
    try:
        validate_model(Path(config["model_path"]))
        # tqdm's default multiprocessing lock creates a named semaphore. A worker
        # killed during inference cannot run its finalizer; use a thread lock here.
        import tqdm
        tqdm.tqdm.set_lock(threading.RLock())
        import torch
        from sentence_transformers import SentenceTransformer
        from transformers.utils import logging as transformer_logging
        from knowledge_agent.retrieval.tokenizer import BgeTokenizer

        torch.set_num_threads(config["threads"])
        torch.set_num_interop_threads(1)
        transformer_logging.disable_progress_bar()
        tokenizer = BgeTokenizer(Path(config["model_path"]) / "tokenizer.json")
        model = SentenceTransformer(config["model_path"], device="cpu", local_files_only=True,
                                    trust_remote_code=False, prompts={"query": "", "document": ""},
                                    model_kwargs={"use_safetensors": True})
        model.max_seq_length = MAX_TOKENS
        model.eval()
        if model.get_embedding_dimension() != DIMENSION:
            raise ValueError("Unexpected pinned model dimension")
        connection.send({"status": "ready"})
        while connection.recv() == "encode":
            request = json.loads((root / "request.json").read_text(encoding="utf-8"))
            texts = request["texts"]
            if any(tokenizer.count(text) > MAX_TOKENS for text in texts):
                connection.send({"status": "error", "code": "EMBEDDING_INPUT_TOO_LONG"})
                continue
            with torch.inference_mode():
                vectors = model.encode(texts, batch_size=config["batch_size"], prompt="",
                                       normalize_embeddings=True, convert_to_numpy=True,
                                       show_progress_bar=False)
            np.save(root / "vectors.npy", np.asarray(vectors, dtype=np.float32), allow_pickle=False)
            connection.send({"status": "ok"})
    except (EOFError, BrokenPipeError):
        pass
    except Exception:
        # Never send exception text, paths, user text, or an unbounded traceback.
        try:
            connection.send({"status": "error", "code": "EMBEDDING_FAILED"})
        except (OSError, EOFError):
            pass
    finally:
        connection.close()


class EmbeddingWorker:
    """One in-flight request; failures reset the worker, close permanently disposes it."""

    def __init__(self, settings: Settings, *, target=run_embedding_worker):
        self.settings = settings
        self._target = target  # Dependency injection for process-boundary tests only.
        self._process = None
        self._connection = None
        self._temporary = None
        self._ready = False
        self._closed = False
        self._guard = threading.Lock()
        self.events: list[dict] = []
        self.generation = 0

    @property
    def pid(self) -> int | None:
        return self._process.pid if self._process is not None else None

    def _event(self, event: str, **fields):
        self.events.append({"event": event, "generation": self.generation, **fields})

    def _launch(self):
        if self._closed:
            raise RetrievalFailure("EMBEDDING_CLOSED", "Embedding 工作进程已关闭。")
        context = multiprocessing.get_context("spawn")
        self._temporary = tempfile.TemporaryDirectory(prefix="ka-embedding-")
        parent, child = context.Pipe()
        self._connection = parent
        process = context.Process(target=self._target, args=(child, self._temporary.name, {
            "model_path": str(self.settings.embedding_model_path.resolve()),
            "batch_size": self.settings.embedding_batch_size, "threads": self.settings.embedding_threads,
        }), daemon=True, name="knowledge-agent-embedding")
        try:
            process.start()
            self._process = process
            self.generation += 1
            self._event("embedding_worker_started", pid=process.pid)
        finally:
            child.close()

    def _stop(self, reason: str):
        process = self._process
        if process is not None:
            pid = process.pid
            if reason == "closed" and process.is_alive():
                try:
                    self._connection.send("stop")
                except (OSError, EOFError):
                    pass
                process.join(self.settings.embedding_stop_timeout)
            if process.is_alive():
                process.terminate()
            process.join(self.settings.embedding_stop_timeout)
            forced = process.is_alive()
            if forced:
                process.kill()
                process.join(self.settings.embedding_stop_timeout)
            if process.is_alive():
                # Do not discard the handle or allow another worker while this one lives.
                self._closed = True
                raise RetrievalFailure("EMBEDDING_STOP_FAILED", "无法回收 embedding 工作进程，停止继续执行。")
            self._event("embedding_worker_stopped", pid=pid, reason=reason,
                        forced_kill=forced, exitcode=process.exitcode)
            process.close()
            self._process = None
        if self._connection is not None:
            self._connection.close()
            self._connection = None
        if self._temporary is not None:
            self._temporary.cleanup()
            self._temporary = None
        self._ready = False

    async def _wait(self, deadline: float) -> dict:
        while True:
            if time.monotonic() >= deadline:
                raise RetrievalFailure("EMBEDDING_TIMEOUT", "本地 embedding 超时，计算进程已终止。", retryable=True)
            if self._closed:
                raise RetrievalFailure("EMBEDDING_CLOSED", "Embedding 工作进程已关闭。")
            if self._connection.poll():
                try:
                    return self._connection.recv()
                except (EOFError, OSError) as exc:
                    raise RetrievalFailure("EMBEDDING_WORKER_EXITED", "Embedding 工作进程异常退出。", retryable=True) from exc
            if not self._process.is_alive():
                raise RetrievalFailure("EMBEDDING_WORKER_EXITED", "Embedding 工作进程异常退出。", retryable=True)
            await asyncio.sleep(min(0.01, max(0, deadline - time.monotonic())))

    async def _request(self, texts: list[str] | None, timeout: float):
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if not self._guard.acquire(blocking=False):
            raise RetrievalFailure("EMBEDDING_BUSY", "Embedding 已有执行中的请求。", retryable=True)
        started = time.monotonic()
        deadline = started + timeout
        try:
            if self._closed:
                raise RetrievalFailure("EMBEDDING_CLOSED", "Embedding 工作进程已关闭。")
            if self._process is None:
                self._launch()
            if not self._ready:
                reply = await self._wait(deadline)
                if reply.get("status") != "ready":
                    raise RetrievalFailure("EMBEDDING_START_FAILED", "无法加载本地 embedding，请检查权重与依赖。")
                self._ready = True
                self._event("embedding_worker_ready", pid=self.pid)
            if texts is None:
                return None
            root = Path(self._temporary.name)
            (root / "request.json").write_text(json.dumps({"texts": texts}, ensure_ascii=False), encoding="utf-8")
            self._connection.send("encode")
            reply = await self._wait(deadline)
            if reply.get("status") != "ok":
                code = reply.get("code")
                if code == "EMBEDDING_INPUT_TOO_LONG":
                    raise RetrievalFailure(code, "Embedding 输入超过 token 上限，未截断。")
                raise RetrievalFailure("EMBEDDING_FAILED", "本地 embedding 计算失败。", retryable=True)
            vectors = np.load(root / "vectors.npy", allow_pickle=False)
            if time.monotonic() >= deadline:
                raise RetrievalFailure("EMBEDDING_TIMEOUT", "本地 embedding 超时，计算进程已终止。", retryable=True)
            self._event("embedding_completed", pid=self.pid, count=len(texts), elapsed_seconds=time.monotonic() - started)
            return vectors
        except asyncio.CancelledError:
            self._stop("cancelled")
            raise
        except BaseException as exc:
            self._stop(getattr(exc, "code", type(exc).__name__))
            if isinstance(exc, (OSError, EOFError)):
                raise RetrievalFailure("EMBEDDING_FAILED", "Embedding 本地通信失败。", retryable=True) from exc
            raise
        finally:
            self._guard.release()

    async def astart(self):
        await self._request(None, self.settings.embedding_startup_timeout)

    def start(self):
        return asyncio.run(self.astart())

    async def aencode(self, texts: list[str], *, timeout: float | None = None) -> np.ndarray:
        if not texts or not all(isinstance(text, str) and text for text in texts):
            raise ValueError("Embedding needs nonempty texts")
        return await self._request(texts, self.settings.embedding_timeout if timeout is None else timeout)

    def encode(self, texts: list[str], *, timeout: float | None = None) -> np.ndarray:
        return asyncio.run(self.aencode(texts, timeout=timeout))

    def close(self):
        self._closed = True
        self._stop("closed")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
