"""Record exactly one current checklist item, with a shell date before start."""

import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "work/temp/workdoc_Sep26-2026_low_profile_d405.md"
OUT = ROOT / "outputs/low-profile-250g"
STATE = Path(__file__).parent / "active-item.json"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["start", "done", "note", "suspend"])
    parser.add_argument("message", nargs="?", default="")
    args = parser.parse_args()
    stamp = subprocess.check_output(
        ["date", "+%Y-%m-%d %H:%M:%S %Z%z"], text=True
    ).strip()
    content = DOC.read_text()
    if args.action == "start":
        if STATE.exists():
            raise RuntimeError("Previous item still active")
        item = next(line for line in content.splitlines() if line.startswith("- [ ]"))
        STATE.write_text(
            json.dumps({"item": item, "started": stamp}, ensure_ascii=False)
        )
        detail = "開始: " + item
    elif args.action == "done":
        state = json.loads(STATE.read_text())
        item = next(line for line in content.splitlines() if line.startswith("- [ ]"))
        assert item == state["item"], "Checklist changed during operation"
        content = content.replace(item, item.replace("[ ]", "[x]", 1), 1)
        detail = "完了: " + item[6:]
        STATE.unlink()
    elif args.action == "suspend":
        state = json.loads(STATE.read_text())
        detail = "ユーザー追記による一時中断: " + state["item"]
        STATE.rename(STATE.with_name("suspended-item.json"))
    else:
        detail = "状況記録"
    date, time = stamp.split(" ", 1)

    def clean(value):
        return value.replace("|", "/").replace("\n", " ")

    content += f"|{date}|{time}|Codex|{clean(detail)}|{clean(args.message)}|\n"
    DOC.write_text(content)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "WORKDOC.md").write_text(content)
    print(stamp, detail, args.message, sep="\n")


if __name__ == "__main__":
    main()
