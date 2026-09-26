"""Update exactly one next workdoc checkbox and its immediate evidence row."""

import argparse
import datetime
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "work/temp/workdoc_Sep26-2026_robot_250g_optimization.md"
STATE = ROOT / "work/optimization/log_state.json"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["start", "done", "note", "sync"])
    parser.add_argument("message", nargs="?", default="")
    args = parser.parse_args()
    now = datetime.datetime.now().astimezone()
    content = DOC.read_text()
    if args.mode == "start":
        if STATE.exists():
            raise RuntimeError("Previous item remains active")
        item = next(line for line in content.splitlines() if line.startswith("- [ ]"))
        STATE.write_text(json.dumps({"item": item, "started": now.isoformat()}))
        print(item)
    elif args.mode == "done":
        active = json.loads(STATE.read_text())
        item = next(line for line in content.splitlines() if line.startswith("- [ ]"))
        if item != active["item"]:
            raise RuntimeError("Checklist order changed")
        content = content.replace(item, item.replace("[ ]", "[x]", 1), 1)
        args.message = f"開始 {active['started']} / 完了: {args.message}"
        STATE.unlink()
    if args.mode != "sync":
        message = args.message.replace("|", "/").replace("\n", "<br>")
        row = f"| {now:%Y-%m-%d} | {now:%H:%M:%S %Z%z} | Codex | {args.mode} | {message} |\n"
        if "\n## 8." in content:
            before, after = content.split("\n## 8.", 1)
            content = before.rstrip() + "\n" + row + "\n## 8." + after
        else:
            content += row
    DOC.write_text(content)
    (ROOT / "outputs/optimization-250g/WORKDOC.md").write_text(content)
    print(
        now.isoformat(),
        args.mode,
        content.count("- [x]"),
        "/",
        content.count("- [ ]") + content.count("- [x]"),
    )


if __name__ == "__main__":
    main()
