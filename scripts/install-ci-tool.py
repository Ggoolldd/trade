"""Install a checksum-pinned CI binary from its official release into a chosen directory."""

import argparse
import hashlib
import io
import json
import platform
import tarfile
import urllib.request
import zipfile
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("name", choices=["actionlint", "gitleaks"])
parser.add_argument("--bin-dir", required=True, type=Path)
args = parser.parse_args()
if platform.machine().lower() not in {"amd64", "x86_64"}:
    raise SystemExit("Only checksum-pinned x86_64 packages are supported")
system = {"Windows": "windows", "Linux": "linux"}.get(platform.system())
if system is None:
    raise SystemExit("Unsupported CI tool platform")
root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / "infrastructure" / "ci-tools.json").read_text(encoding="utf-8"))
tool = manifest["tools"][args.name]
package = tool["packages"][system]
prefix = f"https://github.com/{tool['repository']}/releases/download/{tool['version']}/"
if not package["url"].startswith(prefix):
    raise SystemExit("Release URL does not match pinned official repository/version")
with urllib.request.urlopen(package["url"], timeout=60) as response:
    payload = response.read(100 * 1024 * 1024 + 1)
if len(payload) > 100 * 1024 * 1024 or hashlib.sha256(payload).hexdigest() != package["sha256"]:
    raise SystemExit("CI tool archive checksum/size verification failed")
if system == "windows":
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        binary = archive.read(package["binary"])
else:
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
        stream = archive.extractfile(package["binary"])
        if stream is None:
            raise SystemExit("Expected binary absent from archive")
        binary = stream.read()
args.bin_dir.mkdir(parents=True, exist_ok=True)
target = args.bin_dir / package["binary"]
target.write_bytes(binary)
if system == "linux":
    target.chmod(0o755)
print(f"Installed {args.name} {tool['version']} with verified SHA256")
