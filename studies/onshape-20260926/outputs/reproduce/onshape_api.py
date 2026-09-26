"""Signed Onshape REST calls; private credentials stay outside deliverables."""

import base64
import hashlib
import hmac
import json
import os
import secrets
import urllib.parse
import urllib.request
from email.utils import formatdate
from pathlib import Path

ROOT = Path(os.environ["ONSHAPE_TASK_WORK"]).resolve()
OUTPUT = Path(os.environ["ONSHAPE_TASK_OUTPUT"]).resolve()
ROOT.mkdir(parents=True, exist_ok=True)
OUTPUT.mkdir(parents=True, exist_ok=True)
_project = json.loads((ROOT / "project.json").read_text())
DID, WID, PS, ASM = (_project[k] for k in ("did", "wid", "ps", "asm"))
if (ROOT / "bound-project.json").exists():
    assert json.loads((ROOT / "bound-project.json").read_text()) == _project, (
        "State directory belongs to a different document"
    )
else:
    (ROOT / "bound-project.json").write_text(json.dumps(_project, indent=2))


def api(path, method="GET", body=None, query=None, binary=False):
    credentials = {
        "accessKey": os.environ["ONSHAPE_ACCESS_KEY"],
        "secretKey": os.environ["ONSHAPE_SECRET_KEY"],
    }
    if not path.startswith("/api/"):
        path = "/api/v17" + path
    nonce = secrets.token_hex(16)
    date = formatdate(usegmt=True)
    q = urllib.parse.urlencode(query or {})
    ctype = "application/json"
    canonical = "\n".join([method, nonce, date, ctype, path, q, ""]).lower().encode()  # noqa: FLY002 -- Preserve the archived signature field sequence.
    digest = base64.b64encode(
        hmac.new(credentials["secretKey"].encode(), canonical, hashlib.sha256).digest()
    ).decode()
    headers = {
        "Content-Type": ctype,
        "Accept": "application/json",
        "Date": date,
        "On-Nonce": nonce,
        "Authorization": f"On {credentials['accessKey']}:HmacSHA256:{digest}",
    }
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        "https://cad.onshape.com" + path + ("?" + q if q else ""),
        data=data,
        headers=headers,
        method=method,
    )
    counter = ROOT / "api-count.txt"
    count = int(counter.read_text()) if counter.exists() else 0
    if count >= 1500:
        raise RuntimeError("Task API budget exhausted; stop and inspect")
    counter.write_text(str(count + 1))
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            result = response.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{method} {path}: {e.code}: {e.read().decode()[:2500]}") from None
    if binary:
        return result
    return json.loads(result) if result else None


def save(name, data):
    (ROOT / name).write_text(json.dumps(data, indent=2))


if __name__ == "__main__":
    import sys

    result = api(sys.argv[1])
    save(sys.argv[2], result)
    print("saved", sys.argv[2])
