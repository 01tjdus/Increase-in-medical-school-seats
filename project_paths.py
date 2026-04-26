"""프로젝트 전체에서 공통으로 사용하는 경로 상수.

노트북을 어느 폴더에서 실행하더라도 데이터 입력 위치와 분석 산출물
저장 위치가 흔들리지 않도록, 프로젝트 루트를 기준으로 모든 경로를
한곳에서 정의한다.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ROOT_DIR = ROOT  # 호환 별칭

# 원천·중간 데이터 폴더.
# cafe_only: 카페 단독 크롤/전처리 결과
# blog_only: 블로그 단독 크롤/전처리 결과
# integrated: 블로그와 카페를 합친 분석용 데이터
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

CODE_DIR = ROOT / "notebooks" / "lib"  # 노트북에서 반복 사용하는 보조 함수 모음
NOTEBOOKS_DIR = ROOT / "notebooks"


def bootstrap_code_path(root: Path | None = None) -> Path:
    """과거 스크립트 호환을 위해 `code/` 폴더를 import 경로에 추가한다."""
    base_dir = ROOT if root is None else Path(root)
    code_dir = base_dir / "code"
    if str(code_dir) not in sys.path:
        sys.path.insert(0, str(code_dir))
    return code_dir


def ensure_output_dirs() -> tuple[Path, ...]:
    """분석 산출물이 저장될 폴더들을 미리 생성하고 생성된 경로들을 반환한다."""
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
