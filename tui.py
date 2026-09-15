"""Minimal TUI — delegates to the CLI chat REPL (Python port)."""

import sys

from cli import build_parser, cmd_chat, load_dotenv
from config import load_config


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    load_dotenv()
    p = build_parser()
    args = p.parse_args(["chat"] + list(argv))
    cfg = load_config(getattr(args, "config", None))
    args.agent = getattr(args, "agent", "coder")
    cmd_chat(args, cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())