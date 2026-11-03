"""CLI composition root; business and framework logic live in separate modules."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from knowledge_agent.chat import run_chat
from knowledge_agent.config import load_settings
from knowledge_agent.corpus import FixtureCorpus
from knowledge_agent.errors import CorpusError
from knowledge_agent.knowledge_base import open_indexed_source
from knowledge_agent.retrieval.failures import RetrievalFailure
from knowledge_agent.mock_model import SMOKE_QUESTION
from knowledge_agent.runtime import run_turn


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="企业知识问答 Agent：BM25、向量与混合检索")
    commands = parser.add_subparsers(dest="command", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--mode", choices=["real", "mock"], default=None)
    common.add_argument("--corpus", dest="corpus_path", type=Path, default=None)
    common.add_argument("--prepared", dest="prepared_path", type=Path, default=None,
                        help="使用正式检索／读取工具及该派生块；未指定时保留原冒烟资料源")
    common.add_argument("--output-dir", type=Path, default=None)
    common.add_argument("--retrieval", dest="retrieval_mode", choices=["bm25", "vector", "hybrid"], default=None,
                        help="真实模式默认 hybrid，可显式选择 bm25／vector；Mock 仅支持 bm25")
    common.add_argument("--embedding-model-path", type=Path, default=None)
    common.add_argument("--retrieval-cache-dir", type=Path, default=None)
    common.add_argument("--rrf-k", type=int, default=None)
    common.add_argument("--tokenizer-path", type=Path, default=None)
    commands.add_parser("config", parents=[common], help="显示脱敏后的生效配置")
    smoke = commands.add_parser("smoke", parents=[common], help="单轮接入冒烟；--prepared 启用正式检索／读取工具")
    smoke.add_argument("--question", default=SMOKE_QUESTION)
    chat = commands.add_parser("chat", parents=[common], help="正式资料连续对话；--question 执行单题")
    chat.add_argument("--question", default=None)
    chat.add_argument("--scenario", dest="mock_scenario", choices=["normal", "conflict", "missing", "tool_failure", "recovery", "budget"], default=None,
                      help="显式离线脚本；实际运行所选检索/读取，故障脚本注入本地错误，不证明模型能力")
    chat.add_argument("--history", type=Path, default=None, help="显式导入 schema_version=1 的 user/assistant 历史")
    chat.add_argument("--format", choices=["text", "json"], default="text", dest="output_format")
    prepare = commands.add_parser("prepare", parents=[common], help="准备分块与所选索引；默认仅使用本地资产")
    prepare.add_argument("--download", action="store_true", help="允许显式下载固定版本 tokenizer／BGE 资产")
    evaluate = commands.add_parser("evaluate", parents=[common], help="复用现有离线／真实业务测试，保存独立批次报告")
    evaluate.add_argument("--suite", help="真实模式选 tests/e2e/required 或 extended；Mock 选 tests/e2e/offline；可指定文件或节点")
    evaluate.add_argument("--run-live", action="store_true", help="显式启用真实模型请求，可能消耗 API 额度")
    evaluate.add_argument("--collect-only", action="store_true", help="只列出待执行用例，不执行或计为通过")
    evaluate.add_argument("-k", dest="selection", help="pytest 用例名称筛选表达式")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = create_parser().parse_args(argv)
    try:
        settings = load_settings(mode=args.mode, corpus_path=args.corpus_path, prepared_path=args.prepared_path,
                                 output_dir=args.output_dir, mock_scenario=getattr(args, "mock_scenario", None),
                                 retrieval_mode=args.retrieval_mode, embedding_model_path=args.embedding_model_path,
                                 retrieval_cache_dir=args.retrieval_cache_dir, rrf_k=args.rrf_k,
                                 tokenizer_path=args.tokenizer_path)
        if args.command == "prepare":
            from knowledge_agent.preparation import prepare_knowledge
            from knowledge_agent.trace import RunRecorder
            from uuid import uuid4
            identity = uuid4().hex
            root = settings.output_dir if "output_dir" in settings.model_fields_set else Path("examples/preparation")
            recorder = RunRecorder(root.resolve() / identity, identity)
            recorder.write("input.json", {"config": settings.public_config(), "download_allowed": args.download})
            print(f"准备材料：{recorder.directory}", file=sys.stderr)
            try:
                result = prepare_knowledge(settings, download=args.download)
            except BaseException as exc:
                recorder.write("summary.json", {"status": "cancelled" if isinstance(exc, KeyboardInterrupt) else "failed",
                                               "error_type": type(exc).__name__, "error_code": getattr(exc, "code", None)})
                raise
            result["report_directory"] = str(recorder.directory)
            recorder.write("summary.json", result)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 1 if result["status"] == "partial" else 0
        if args.command == "evaluate":
            if args.corpus_path is not None or args.prepared_path is not None:
                raise ValueError("evaluate 使用 suite 固定的合成资料，不接受 --corpus／--prepared 覆盖。")
            from knowledge_agent.evaluation import evaluate
            print("开始评估；测试输出与运行证据将保存到独立批次目录。", file=sys.stderr)
            result = evaluate(settings, suite=args.suite, run_live=args.run_live, collect_only=args.collect_only,
                              selection=args.selection,
                              output_dir=settings.output_dir if "output_dir" in settings.model_fields_set else None)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return result["exit_code"]
        if args.command == "config":
            print(json.dumps(settings.public_config(), ensure_ascii=False, indent=2))
            return 0
        if args.command == "chat":
            if settings.mode == "mock" and settings.mock_scenario is None:
                raise ValueError("MOCK_SCENARIO_UNSUPPORTED：正式离线 chat 必须显式指定 --scenario；只支持已声明的脚本输入。")
            if settings.prepared_path is None:
                raise ValueError("chat 需要 --corpus 与匹配的 --prepared，或在配置中设置正式资料路径。")
            with open_indexed_source(settings) as source:
                return run_chat(settings, source, question=args.question, history_path=args.history,
                                output_format=args.output_format)
        if settings.mode == "mock" and settings.prepared_path is not None:
            print("MOCK_SCENARIO_UNSUPPORTED：smoke 的 Mock 模式仅支持内置冒烟资料；使用正式检索与读取工具的离线场景，请按 README 运行 chat --mode mock --scenario normal 或 evaluate --mode mock。", file=sys.stderr)
            return 2
        if settings.mode == "mock" and args.question != SMOKE_QUESTION:
            print("MOCK_SCENARIO_UNSUPPORTED：当前仅支持文档中声明的固定冒烟问题。", file=sys.stderr)
            return 2
        if settings.prepared_path is not None:
            with open_indexed_source(settings) as source:
                show_retrieval_warnings(source)
                result = asyncio.run(run_turn(args.question, settings, source))
        else:
            if settings.retrieval_mode is not None:
                raise ValueError("显式检索模式需要正式 --corpus／--prepared；原 smoke_fixture 不支持模式切换。")
            source = FixtureCorpus.load(settings.corpus_path, settings.max_tool_chars)
            result = asyncio.run(run_turn(args.question, settings, source))
        print(result.model_dump_json(indent=2))
        print(f"运行材料：{settings.output_dir / settings.mode / result.run_id}", file=sys.stderr)
        return 1 if result.result.status == "incomplete" else 0
    except ValidationError as exc:
        if any(error["type"] == "mock_retrieval_mode" for error in exc.errors(include_input=False)):
            print("Mock 仅支持 BM25；请使用 --retrieval bm25，或移除环境／.env 中的非 BM25 检索配置。", file=sys.stderr)
            return 2
        # Pydantic's default string includes offending values, which can be secrets.
        fields = ", ".join(".".join(map(str, error["loc"])) for error in exc.errors(include_input=False))
        print(f"配置错误，请检查字段：{fields}。", file=sys.stderr)
        return 2
    except (CorpusError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except RetrievalFailure as exc:
        print(f"{exc.code}：{exc}", file=sys.stderr)
        return 2
    except OSError:
        print("无法读取或保存运行材料，请检查路径与写入权限；不宣称材料已保存。", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("已退出；处理中断记录已尽力保存。", file=sys.stderr)
        return 130


def show_retrieval_warnings(source):
    for error in getattr(source.index, "startup_errors", ()):
        print(f"混合检索分支 {error['target']['id']} 不可用（{error['code']}）；"
              "查询将报告 partial，此运行不计为完整 hybrid。", file=sys.stderr)
