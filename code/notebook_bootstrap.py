"""노트북 첫 셀에서 프로젝트 루트·code 경로를 sys.path에 넣고 ROOT Path를 반환합니다."""
from __future__ import annotations

import sys
from pathlib import Path


def setup_paths() -> Path:
    """
    현재 작업 디렉터리에서 위로 올라가며 `project_paths.py`가 있는 디렉터리를 루트로 삼습니다.
    `notebooks/`, `notebooks/01_cafe/` 등 어디서 실행해도 동일하게 동작합니다.
    """
    cwd = Path.cwd().resolve()
    for d in [cwd, *cwd.parents]:
        if (d / "project_paths.py").is_file():
            root = d
            for p in (str(root), str(root / "code")):
                if p not in sys.path:
                    sys.path.insert(0, p)
            return root
    raise FileNotFoundError(
        f"project_paths.py를 찾지 못했습니다. cwd={cwd}. Jupyter 작업 폴더를 프로젝트 루트 또는 notebooks/ 하위로 두세요."
    )
