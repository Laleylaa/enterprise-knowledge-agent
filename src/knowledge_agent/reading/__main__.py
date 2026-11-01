"""Direct source reading CLI; no model credentials or Agent calls required."""

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from knowledge_agent.config import load_settings
from knowledge_agent.errors import CorpusError
from knowledge_agent.reading.session import create_read_tool


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="独立读取原文；不调用模型或 Agent。")
    parser.add_argument("--corpus", required=True, type=Path)
    parser.add_argument("--prepared", required=True, type=Path)
    parser.add_argument("--doc-id", required=True)
    selector = parser.add_mutually_exclusive_group()
    selector.add_argument("--section-id")
    selector.add_argument("--chunk-id")
    parser.add_argument("--purpose", default="读取可核对的制度原文")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--tokenizer-path", type=Path)
    args = parser.parse_args(argv)
    try:
        settings = load_settings(output_dir=args.output_dir, tokenizer_path=args.tokenizer_path)
        tool = create_read_tool(settings, args.corpus, args.prepared)
        result = tool.execute({"doc_id": args.doc_id, "purpose": args.purpose,
                               "section_id": args.section_id, "chunk_id": args.chunk_id}, call_id="read-1")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"单工具运行材料：{tool.recorder.directory}", file=sys.stderr)
        return 1 if result["status"] == "error" else 0
    except ValidationError as exc:
        fields = [".".join(map(str, e["loc"])) for e in exc.errors(include_input=False)]
        print(f"配置不合法，请检查：{', '.join(fields)}", file=sys.stderr)
        return 2
    except CorpusError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except OSError:
        print("无法读取资料或保存运行材料，请检查路径和权限。", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
