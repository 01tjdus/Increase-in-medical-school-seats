#!/usr/bin/env python3
"""
구간별 고착어 CSV(`sticky_keyword_candidates_section{n}.csv`)를 읽고,
sticky_score가 기준값 이상인 단어를 해당 구간 로컬 불용어 사전에 반영합니다.

기준값 변경:
  - 이 파일 상단의 DEFAULT_MIN_STICKY_SCORE 를 바꾸거나
  - 실행 시: python notebooks/lib/append_sticky_local_stopwords.py --min-sticky 40
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

# 고착어 점수가 이 값 이상이면 워드클라우드에서 반복적으로 크게 보이는 단어로 보고
# 구간별 로컬 불용어 후보에 포함한다.
DEFAULT_MIN_STICKY_SCORE = 50.0


def _project_root() -> Path:
    """현재 파일 위치에서 프로젝트 루트(project_paths.py가 있는 폴더)를 찾는다."""
    here = Path(__file__).resolve()
    for d in [here.parent, *here.parents]:
        if (d / "project_paths.py").is_file():
            return d
    raise FileNotFoundError("project_paths.py 를 찾을 수 없습니다.")


def existing_words_from_txt(path: Path) -> set[str]:
    """기존 로컬 불용어 파일에 이미 들어 있는 단어를 읽어 중복 추가를 막는다."""
    out: set[str] = set()
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        w = line.strip()
        if not w or w.startswith("#"):
            continue
        out.add(w)
    return out


def sticky_words_at_least(csv_path: Path, min_score: float) -> list[str]:
    """sticky_score 기준을 넘는 후보 단어를 점수 높은 순서로 반환한다."""
    df = pd.read_csv(csv_path, encoding="utf-8-sig", index_col=0)
    if "sticky_score" not in df.columns:
        raise KeyError(f"sticky_score column missing: {csv_path}")
    sub = df.loc[df["sticky_score"] >= min_score].sort_values("sticky_score", ascending=False)
    return [str(i).strip() for i in sub.index if str(i).strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Append high-sticky terms to section local stopword files.")
    parser.add_argument(
        "--min-sticky",
        type=float,
        default=None,
        metavar="SCORE",
        help=f"sticky_score >= SCORE (default: {DEFAULT_MIN_STICKY_SCORE})",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print counts only; do not write files.")
    args = parser.parse_args()

    min_score = float(args.min_sticky) if args.min_sticky is not None else float(DEFAULT_MIN_STICKY_SCORE)

    root = _project_root()
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / "notebooks" / "lib"))
    from project_paths import OUTPUTS_ANALYSIS_TFIDF, STOPWORDS_DIR

    out_dir = OUTPUTS_ANALYSIS_TFIDF
    stop_dir = STOPWORDS_DIR

    for section in (1, 2, 3, 4):
        csv_path = out_dir / f"sticky_keyword_candidates_section{section}.csv"
        txt_path = stop_dir / f"stopwords_local_section{section}.txt"
        if not csv_path.is_file():
            print(f"section {section}: CSV 없음 → 건너뜀 ({csv_path})")
            continue
        candidates = sticky_words_at_least(csv_path, min_score)
        have = existing_words_from_txt(txt_path)
        new_words = [w for w in candidates if w not in have]
        print(f"section {section}: min_sticky={min_score} 후보 {len(candidates)}개, 파일에 없어서 추가 {len(new_words)}개")
        if args.dry_run:
            continue
        if not new_words:
            continue
        block = (
            f"\n# --- sticky_score>={min_score:g} 기준 반영 단어 ---\n"
            + "\n".join(new_words)
            + "\n"
        )
        body = txt_path.read_text(encoding="utf-8") if txt_path.is_file() else ""
        if body and not body.endswith("\n"):
            body += "\n"
        txt_path.write_text(body + block, encoding="utf-8")
        print(f"  → 쓰기 완료: {txt_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
