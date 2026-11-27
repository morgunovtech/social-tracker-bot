"""The Claude skill that walks a newcomer through the setup
(plugins/social-tracker-setup) installs from the marketplace in the repo root
and uploads to claude.ai as a zip: the manifests agree, the frontmatter has
only the keys claude.ai accepts and fits its limits, every reference page is
linked and exists."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"
PLUGIN = ROOT / "plugins" / "social-tracker-setup"
SKILL = PLUGIN / "skills" / "install-social-tracker"

# claude.ai's upload refuses any other key; its help page limits name to 64
# characters and description to 200 (support.claude.com, «How to create custom skills»).
UPLOAD_KEYS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}


def _frontmatter() -> dict[str, str]:
    text = (SKILL / "SKILL.md").read_text("utf-8")
    assert text.startswith("---\n"), "SKILL.md must start with frontmatter"
    block = text.split("---\n", 2)[1]
    fields = {}
    for line in block.splitlines():
        key, sep, value = line.partition(":")
        assert sep, f"not a «key: value» line: {line!r}"
        value = value.strip()
        if value.startswith('"'):
            assert value.endswith('"') and '"' not in value[1:-1], value
            value = value[1:-1]
        else:
            assert ": " not in value, f"{key}: a «: » inside an unquoted value breaks YAML"
        fields[key.strip()] = value
    return fields


def test_the_frontmatter_is_what_claude_ai_accepts():
    fields = _frontmatter()
    assert set(fields) <= UPLOAD_KEYS, set(fields) - UPLOAD_KEYS
    assert fields["name"] == SKILL.name                       # the folder is named after the skill
    assert len(fields["name"]) <= 64 and 0 < len(fields["description"]) <= 200


def test_the_marketplace_and_the_plugin_agree():
    market = json.loads(MARKETPLACE.read_text("utf-8"))
    plugin = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text("utf-8"))
    assert {"name", "owner", "plugins"} <= set(market) and market["owner"]["name"]
    [entry] = market["plugins"]
    assert entry["name"] == plugin["name"] == PLUGIN.name
    assert entry["source"] == "./plugins/social-tracker-setup" and (ROOT / entry["source"]).is_dir()
    assert entry.get("version") == plugin["version"]


def test_every_reference_is_linked_and_exists():
    text = (SKILL / "SKILL.md").read_text("utf-8")
    linked = set(re.findall(r"\]\((references/[^)]+\.md)\)", text))
    present = {f"references/{p.name}" for p in (SKILL / "references").glob("*.md")}
    assert linked == present, (linked - present, present - linked)


def test_the_upload_zip_has_the_skill_folder_at_its_root(tmp_path):
    import importlib.util
    import zipfile

    spec = importlib.util.spec_from_file_location("package_skill", ROOT / "scripts" / "package_skill.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    names = zipfile.ZipFile(module.package(tmp_path)).namelist()
    assert "install-social-tracker/SKILL.md" in names
    assert all(name.startswith("install-social-tracker/") for name in names)
    assert "install-social-tracker/references/railway.md" in names
