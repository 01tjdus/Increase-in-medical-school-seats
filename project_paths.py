from __future__ import annotations

import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
CODE_DIR = ROOT_DIR / "code"
CONFIG_DIR = ROOT_DIR / "config"
CONFIG_STOPWORDS = CONFIG_DIR / "stopwords"
DATA_DIR = ROOT_DIR / "data"
DATA_BLOG_ONLY = DATA_DIR / "blog_only"
DATA_INTEGRATED = DATA_DIR / "integrated"
NOTEBOOKS_DIR = ROOT_DIR / "notebooks"
OUTPUTS_DIR = ROOT_DIR / "outputs"
OUTPUTS_PIPELINE = OUTPUTS_DIR / "pipeline"
OUTPUTS_PIPELINE_DATASETS = OUTPUTS_PIPELINE / "datasets"
OUTPUTS_PIPELINE_KMEANS = OUTPUTS_PIPELINE / "kmeans"
OUTPUTS_PIPELINE_LDA = OUTPUTS_PIPELINE / "lda"
OUTPUTS_PIPELINE_STOPWORDS = OUTPUTS_PIPELINE / "stopwords"
OUTPUTS_PIPELINE_TFIDF = OUTPUTS_PIPELINE / "tfidf"
OUTPUTS_PIPELINE_WORDCLOUD = OUTPUTS_PIPELINE / "wordcloud"
OUTPUTS_PIPELINE_WORDCLOUD_FILTERED = OUTPUTS_PIPELINE_WORDCLOUD / "filtered"
OUTPUTS_PIPELINE_WORDCLOUD_RAW = OUTPUTS_PIPELINE_WORDCLOUD / "raw"


def bootstrap_code_path(root: Path | None = None) -> Path:
    base_dir = ROOT_DIR if root is None else Path(root)
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
