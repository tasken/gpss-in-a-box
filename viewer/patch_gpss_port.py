#!/usr/bin/env python3
"""Write config.json with an internal HTTP port (Docker viewer proxy)."""
import json
import sys


def main() -> None:
    src, dst, port, addr = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
    cfg = json.loads(open(src, encoding="utf-8").read())
    cfg.setdefault("http", {})
    cfg["http"]["port"] = port
    cfg["http"]["listening_addr"] = addr
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
