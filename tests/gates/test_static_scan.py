from pathlib import Path
from tools.gates.static_scan import scan_tree

def test_static_scan_excludes_venv(tmp_path: Path):
    # create a fake venv file containing forbidden token; should be excluded
    venv_dir = tmp_path / ".venv" / "lib"
    venv_dir.mkdir(parents=True)
    (venv_dir / "x.py").write_text("import os\nos.system('rm -rf /')\n", encoding="utf-8")
    findings = scan_tree(tmp_path)
    assert findings == []
