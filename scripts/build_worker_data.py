"""Generate cloudflare-worker/src/data.json (categories, freshness limits, email domains) from schema/categories.yml."""

import json
import pathlib

import yaml

root = pathlib.Path(__file__).resolve().parents[1]
cats = yaml.safe_load((root / "schema" / "categories.yml").read_text(encoding="utf-8"))
(root / "cloudflare-worker" / "src" / "data.json").write_text(json.dumps(cats, indent=1), encoding="utf-8")
print("written")
