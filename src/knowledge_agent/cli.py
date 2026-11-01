"""CLI composition root; business and framework logic live in separate modules."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from knowledge_agent.config import load_settings
from knowledge_agent.corpus import FixtureCorpus
from knowledge_agent.errors import CorpusError
from knowledge_agent.mock_model import SMOKE_QUESTION
from knowledge_agent.runtime import run_turn


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="企业知识问答 Agent：当前为最小接入冒烟阶段")
    commands = parser.add_subparsers(dest="command", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--mode", choices=["real", "mock"], default=None)
    common.add_argument("--corpus", dest="corpus_path", type=Path, default=None)
    common.add_argument("--output-dir", type=Path, default=None)
    commands.add_parser("config", parents=[common], help="显示脱敏后的生效配置")
    smoke = commands.add_parser("smoke", parents=[common], help="单题冒烟；固定资料源，尚非完整业务检索")
    smoke.add_argument("--question", default=SMOKE_QUESTION)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = create_parser().parse_args(argv)
    try:
        settings = load_settings(mode=args.mode, corpus_path=args.corpus_path, output_dir=args.output_dir)
        if args.command == "config":
            print(json.dumps(settings.public_config(), ensure_ascii=False, indent=2))
            return 0
        if settings.mode == "mock" and args.question != SMOKE_QUESTION:
            print("MOCK_SCENARIO_UNSUPPORTED：当前仅支持文档中声明的固定冒烟问题。", file=sys.stderr)
            return 2
        source = FixtureCorpus.load(settings.corpus_path, settings.max_tool_chars)
        result = asyncio.run(run_turn(args.question, settings, source))
        print(result.model_dump_json(indent=2))
        print(f"运行材料：{settings.output_dir / settings.mode / result.run_id}", file=sys.stderr)
        return 1 if result.result.status == "incomplete" else 0
    except ValidationError as exc:
        # Pydantic's default string includes offending values, which can be secrets.
        fields = ", ".join(".".join(map(str, error["loc"])) for error in exc.errors(include_input=False))
        print(f"配置错误，请检查字段：{fields}。", file=sys.stderr)
        return 2
    except (CorpusError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except OSError:
        print("无法读取或保存运行材料，请检查路径与写入权限；不宣称材料已保存。", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("已退出；处理中断记录已尽力保存。", file=sys.stderr)
        return 130
