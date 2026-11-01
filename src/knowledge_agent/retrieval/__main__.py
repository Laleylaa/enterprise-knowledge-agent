"""Explicit preparation and direct search commands, independent of agent CLI."""

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from knowledge_agent.config import load_settings
from knowledge_agent.document_loader import load_documents
from knowledge_agent.errors import CorpusError
from knowledge_agent.retrieval.session import create_search_tool
from knowledge_agent.retrieval.snapshot import prepare_documents, save_prepared
from knowledge_agent.retrieval.tokenizer import TOKENIZER_SPEC, download_tokenizer


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="单独运行知识检索工具；不调用模型或 Agent。")
    commands = parser.add_subparsers(dest="command", required=True)
    download = commands.add_parser("download-tokenizer", help="显式下载固定版本 tokenizer，不下载模型权重")
    download.add_argument("--tokenizer-path", type=Path)
    for command in ["prepare", "search"]:
        sub = commands.add_parser(command)
        sub.add_argument("--corpus", required=True, type=Path)
        sub.add_argument("--prepared", required=True, type=Path)
        sub.add_argument("--tokenizer-path", type=Path)
        if command == "search":
            sub.add_argument("--query", required=True)
            sub.add_argument("--purpose", default="查找员工制度原文")
            sub.add_argument("--doc-ids", nargs="+")
            sub.add_argument("--limit", type=int, default=5)
            sub.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    try:
        settings = load_settings(tokenizer_path=args.tokenizer_path,
                                 output_dir=getattr(args, "output_dir", None))
        if args.command == "download-tokenizer":
            download_tokenizer(settings.tokenizer_path)
            print(json.dumps(TOKENIZER_SPEC, ensure_ascii=False))
        elif args.command == "prepare":
            bundle = prepare_documents(load_documents(args.corpus), settings)
            save_prepared(bundle, args.prepared)
            print(json.dumps({"corpus_hash": bundle.corpus_hash, "chunks": len(bundle.chunks),
                              "prepared": str(args.prepared)}, ensure_ascii=False))
        else:
            tool = create_search_tool(settings, args.corpus, args.prepared)
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
    except OSError:
        print("无法准备资料或读写运行材料，请检查网络、路径和权限。", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
