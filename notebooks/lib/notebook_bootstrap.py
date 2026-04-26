"""노트북 실행 위치를 프로젝트 루트 기준으로 맞추는 보조 모듈.

Jupyter는 실행 위치가 열어 둔 노트북 폴더에 따라 달라질 수 있다.
이 함수는 현재 작업 폴더에서 위로 올라가며 `project_paths.py`를 찾고,
프로젝트 루트와 `notebooks/lib`를 import 경로에 추가한다.
"""
from __future__ import annotations

import sys
from pathlib import Path


def setup_paths() -> Path:
    """
    현재 작업 디렉터리에서 위로 올라가며 `project_paths.py`가 있는 디렉터리를 루트로 삼습니다.
    `notebooks/lib`에 있는 유틸 모듈을 import할 수 있도록 경로를 추가합니다.
    """
    cwd = Path.cwd().resolve()
    for d in [cwd, *cwd.parents]:
        if (d / "project_paths.py").is_file():
            root = d
            lib = root / "notebooks" / "lib"
            # 노트북에서 project_paths.py와 공통 유틸을 바로 import하기 위한 경로 설정.
            for p in (str(root), str(lib)):
                if p not in sys.path:
                    sys.path.insert(0, p)
            return root
    raise FileNotFoundError(
        f"project_paths.py를 찾지 못했습니다. cwd={cwd}. Jupyter 작업 폴더를 프로젝트 루트 또는 notebooks/ 하위로 두세요."
    )
