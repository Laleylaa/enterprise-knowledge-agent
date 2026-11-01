"""Explicit preparation and direct search commands, independent of agent CLI."""

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from knowledge_agent.config import load_settings
from knowledge_agent.errors import CorpusError
from knowledge_agent.retrieval.session import create_search_tool
from knowledge_agent.retrieval.tokenizer import TOKENIZER_SPEC, download_tokenizer
from knowledge_agent.retrieval.failures import RetrievalFailure


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="单独运行知识检索工具；不调用模型或 Agent。")
    commands = parser.add_subparsers(dest="command", required=True)
    download = commands.add_parser("download-tokenizer", help="显式下载固定版本 tokenizer，不下载模型权重")
    download.add_argument("--tokenizer-path", type=Path)
    model_download = commands.add_parser("download-model", help="显式下载并校验固定版本本地 BGE 权重")
    model_download.add_argument("--embedding-model-path", type=Path)
    for command in ["prepare", "search"]:
        sub = commands.add_parser(command)
        sub.add_argument("--corpus", required=True, type=Path)
        sub.add_argument("--prepared", required=True, type=Path)
        sub.add_argument("--tokenizer-path", type=Path)
        sub.add_argument("--retrieval", choices=["bm25", "vector", "hybrid"], default=None)
        sub.add_argument("--rrf-k", type=int, default=None)
        sub.add_argument("--embedding-model-path", type=Path)
        sub.add_argument("--retrieval-cache-dir", type=Path)
        if command == "search":
            sub.add_argument("--query", required=True)
            sub.add_argument("--purpose", default="查找员工制度原文")
            sub.add_argument("--doc-ids", nargs="+")
            sub.add_argument("--limit", type=int, default=5)
            sub.add_argument("--output-dir", type=Path)
        else:
            sub.add_argument("--download", action="store_true")
    args = parser.parse_args(argv)
    try:
        settings = load_settings(tokenizer_path=getattr(args, "tokenizer_path", None),
                                 embedding_model_path=getattr(args, "embedding_model_path", None),
                                 retrieval_cache_dir=getattr(args, "retrieval_cache_dir", None),
                                 output_dir=getattr(args, "output_dir", None),
                                 retrieval_mode=getattr(args, "retrieval", None), rrf_k=getattr(args, "rrf_k", None))
        retrieval = settings.selected_retrieval
        if retrieval in {"vector", "hybrid"} and "tokenizer_path" not in settings.model_fields_set and (settings.embedding_model_path / "tokenizer.json").is_file():
            settings = settings.model_copy(update={"tokenizer_path": settings.embedding_model_path / "tokenizer.json"})
        if args.command == "download-tokenizer":
            download_tokenizer(settings.tokenizer_path)
            print(json.dumps(TOKENIZER_SPEC, ensure_ascii=False))
        elif args.command == "download-model":
            from knowledge_agent.retrieval.model_assets import download_model
            print(json.dumps(download_model(settings.embedding_model_path), ensure_ascii=False, indent=2))
        elif args.command == "prepare":
            from knowledge_agent.preparation import prepare_knowledge
            result = prepare_knowledge(settings.model_copy(update={"corpus_path": args.corpus,
                                       "prepared_path": args.prepared}), download=args.download)
            print(json.dumps(result, ensure_ascii=False))
            return 1 if result["status"] == "partial" else 0
        else:
            with create_search_tool(settings, args.corpus, args.prepared, retrieval=retrieval) as tool:
                for error in getattr(tool.index, "startup_errors", ()):
                    print(f"混合检索分支 {error['target']['id']} 不可用，查询将报告 partial。", file=sys.stderr)
                result = tool.execute({"query": args.query, "purpose": args.purpose,
                                       "doc_ids": args.doc_ids, "limit": args.limit}, call_id="search-1")
                print(json.dumps(result, ensure_ascii=False, indent=2))
                print(f"单工具运行材料：{tool.recorder.directory}", file=sys.stderr)
                return 1 if result["status"] == "error" else 0
        return 0
    except ValidationError as exc:
        fields = [".".join(map(str, e["loc"])) for e in exc.errors(include_input=False)]
        print(f"配置不合法，请检查：{', '.join(fields)}", file=sys.stderr)
        return 2
    except CorpusError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except RetrievalFailure as exc:
        print(f"{exc.code}：{exc}", file=sys.stderr)
        return 2
    except OSError:
        print("无法准备资料或读写运行材料，请检查网络、路径和权限。", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("已取消；本地 embedding 工作进程已回收。", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
