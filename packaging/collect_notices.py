"""Collect original dependency notices and a version inventory beside the portable EXE."""

import argparse
import importlib.metadata
import json
import shutil
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("destination", type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
destination = args.destination.resolve()
destination.mkdir(parents=True, exist_ok=True)
shutil.copytree(root / "LICENSES", destination / "LICENSES", dirs_exist_ok=True)
for name in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
    shutil.copy2(root / name, destination / name)
shutil.copy2(root / "packaging/portable-readme.txt", destination / "先读我.txt")
inventory = []
for distribution in importlib.metadata.distributions():
    name = distribution.metadata["Name"]
    inventory.append(
        {
            "name": name,
            "version": distribution.version,
            "license": distribution.metadata.get("License-Expression")
            or distribution.metadata.get("License", ""),
        }
    )
    for entry in distribution.files or []:
        if any(
            word in entry.name.lower() for word in ("license", "copying", "notice", "copyright")
        ):
            source = Path(distribution.locate_file(entry))
            if source.is_file():
                target = (
                    destination / "LICENSES" / "dependencies" / name / str(entry).replace("../", "")
                )
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
python_license = Path(sys.base_prefix) / "LICENSE.txt"
if python_license.exists():
    shutil.copy2(python_license, destination / "LICENSES/Python-LICENSE.txt")
(destination / "DEPENDENCIES.json").write_text(
    json.dumps(sorted(inventory, key=lambda item: item["name"].lower()), indent=2), encoding="utf8"
)
print(f"Collected notices for {len(inventory)} build-environment distributions.")
