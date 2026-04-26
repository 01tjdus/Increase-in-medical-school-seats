"""프로젝트 루트 및 데이터·설정·산출물 경로 (노트북·스크립트 공통)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ROOT_DIR = ROOT  # 호환 별칭

# 데이터 (실제 폴더는 `cafe_only` / `integrated`; `blog_only`는 원격 구조와의 호환용)
DATA_CAFE_ONLY = ROOT / "data" / "cafe_only"
DATA_INTEGRATED = ROOT / "data" / "integrated"
DATA_BLOG_ONLY = ROOT / "data" / "blog_only"

CONFIG_DIR = ROOT / "config"
CONFIG_STOPWORDS = CONFIG_DIR / "stopwords"

OUTPUTS_DIR = ROOT / "outputs"
OUTPUTS_PIPELINE = OUTPUTS_DIR / "pipeline"
OUTPUTS_PIPELINE_DATASETS = OUTPUTS_PIPELINE / "datasets"
OUTPUTS_PIPELINE_KMEANS = OUTPUTS_PIPELINE / "kmeans"
OUTPUTS_PIPELINE_LDA = OUTPUTS_PIPELINE / "lda"
OUTPUTS_PIPELINE_STOPWORDS = OUTPUTS_PIPELINE / "stopwords"
OUTPUTS_PIPELINE_TFIDF = OUTPUTS_PIPELINE / "tfidf"
OUTPUTS_PIPELINE_WORDCLOUD = OUTPUTS_PIPELINE / "wordcloud"
OUTPUTS_PIPELINE_WORDCLOUD_FILTERED = OUTPUTS_PIPELINE_WORDCLOUD / "filtered"
OUTPUTS_PIPELINE_WORDCLOUD_RAW = OUTPUTS_PIPELINE_WORDCLOUD / "raw"

CODE_DIR = ROOT / "notebooks" / "lib"  # 공통 노트북 유틸
NOTEBOOKS_DIR = ROOT / "notebooks"


def bootstrap_code_path(root: Path | None = None) -> Path:
    base_dir = ROOT if root is None else Path(root)
    code_dir = base_dir / "code"
    if str(code_dir) not in sys.path:
        sys.path.insert(0, str(code_dir))
    return code_dir


def ensure_output_dirs() -> tuple[Path, ...]:
    output_dirs = (
        OUTPUTS_PIPELINE,
        OUTPUTS_PIPELINE_DATASETS,
        OUTPUTS_PIPELINE_KMEANS,
        OUTPUTS_PIPELINE_LDA,
        OUTPUTS_PIPELINE_STOPWORDS,
        OUTPUTS_PIPELINE_TFIDF,
        OUTPUTS_PIPELINE_WORDCLOUD,
        OUTPUTS_PIPELINE_WORDCLOUD_FILTERED,
        OUTPUTS_PIPELINE_WORDCLOUD_RAW,
    )
    for path in output_dirs:
        path.mkdir(parents=True, exist_ok=True)
    return output_dirs
