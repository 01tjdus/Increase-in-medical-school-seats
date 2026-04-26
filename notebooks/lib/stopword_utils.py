"""분기별 불용어·TF-IDF 분석에서 반복 사용하는 함수 모음.

노트북 안에 동일한 전처리 로직이 흩어지지 않도록, 명사 리스트 정리,
공통·로컬 불용어 적용, TF-IDF 행렬 생성, 구간별 고착어 후보 산출을
이 파일에 모아 두었다.
"""
from __future__ import annotations

import ast
import math
import re
from pathlib import Path
from typing import Iterable, Set

import numpy as np
import pandas as pd


def load_stopword_files(*paths: Path) -> Set[str]:
    """여러 UTF-8 텍스트 사전을 읽어 합집합(빈 줄·# 주석 제외)."""
    seen: Set[str] = set()
    for p in paths:
        if not p.is_file():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            w = line.strip()
            if not w or w.startswith("#"):
                continue
            seen.add(w)
    return seen


def ensure_token_list(x) -> list:
    """명사 컬럼 값을 list[str]로 통일."""
    if x is None:
        return []
    try:
        if pd.isna(x):
            return []
    except (TypeError, ValueError):
        pass
    if isinstance(x, float) and math.isnan(x):
        return []
    if isinstance(x, list):
        return [t for t in x if isinstance(t, str)]
    if isinstance(x, str):
        try:
            v = ast.literal_eval(x)
            if isinstance(v, list):
                return [t for t in v if isinstance(t, str)]
        except (ValueError, SyntaxError):
            pass
    return []


def filter_stopwords(tokens: Iterable[str], stopwords: Set[str], min_len: int = 2) -> list:
    """1글자 및 사전 단어 제거(리스트 컴프, in-place remove 미사용)."""
    return [t for t in tokens if isinstance(t, str) and len(t) >= min_len and t not in stopwords]


def snapshot_noun_columns(df: pd.DataFrame) -> None:
    """title/document/comment 명사 컬럼을 *_raw 로 얕은 복사가 아닌 리스트 복사로 저장."""
    for col in ("title_token_noun", "document_token_noun", "comment_token_noun"):
        raw = f"{col}_raw"
        df[raw] = df[col].apply(lambda x: list(ensure_token_list(x)))


def apply_global_clean(
    df: pd.DataFrame,
    stopwords: Set[str],
    src_suffix: str = "_raw",
    dst_suffix: str = "_clean",
) -> None:
    """전체 문서에 공통 불용어를 한 번 적용해 *_clean 컬럼을 만든다."""
    for base in ("title_token_noun", "document_token_noun", "comment_token_noun"):
        src, dst = f"{base}{src_suffix}", f"{base}{dst_suffix}"
        if src not in df.columns:
            raise KeyError(f"missing {src}")
        df[dst] = df[src].apply(lambda xs: filter_stopwords(ensure_token_list(xs), stopwords))


def row_merged_tokens(
    row: pd.Series,
    suffix: str = "_clean",
    bases: tuple = ("title_token_noun", "document_token_noun", "comment_token_noun"),
) -> str:
    """TF-IDF용: 행의 명사 리스트를 공백 구분 문자열로 결합."""
    parts: list[str] = []
    for base in bases:
        col = f"{base}{suffix}"
        parts.extend(ensure_token_list(row.get(col)))
    return " ".join(parts)


def parse_comment_list_cell(val) -> list:
    """comment_list 셀을 list[dict]로."""
    if val is None:
        return []
    try:
        if pd.isna(val):
            return []
    except (TypeError, ValueError):
        pass
    if isinstance(val, float) and math.isnan(val):
        return []
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        try:
            v = ast.literal_eval(val)
            return v if isinstance(v, list) else []
        except (ValueError, SyntaxError):
            return []
    return []


def safe_int_comment_cnt(val) -> int:
    """댓글 수처럼 숫자형이어야 하는 값을 안전하게 정수로 변환한다."""
    if val is None or val == "":
        return 0
    if isinstance(val, (int, np.integer)):
        return int(val)
    if isinstance(val, float) and not math.isnan(val):
        return int(val)
    s = str(val).strip()
    if not s:
        return 0
    try:
        return int(float(s))
    except ValueError:
        return 0


def load_local_stopwords_for_section(stopwords_dir: Path, section: int) -> Set[str]:
    """특정 구간(section)에 대응하는 로컬 불용어 파일을 읽는다."""
    return load_stopword_files(stopwords_dir / f"stopwords_local_section{int(section)}.txt")


def apply_local_clean(
    df: pd.DataFrame,
    stopwords_dir: Path,
    src_suffix: str = "_clean",
    dst_suffix: str = "_final",
) -> None:
    """section 값(1~4)에 따라 `stopwords_dir`의 섹션별 로컬 사전을 추가 적용."""
    local_cache: dict[int, Set[str]] = {}

    def local_set(sec: int) -> Set[str]:
        sec = int(sec)
        if sec not in local_cache:
            local_cache[sec] = load_local_stopwords_for_section(stopwords_dir, sec)
        return local_cache[sec]

    for base in ("title_token_noun", "document_token_noun", "comment_token_noun"):
        src = f"{base}{src_suffix}"
        dst = f"{base}{dst_suffix}"

        def _apply_row(row: pd.Series) -> list:
            sw = local_set(int(row["section"]))
            return filter_stopwords(ensure_token_list(row[src]), sw, min_len=2)

        df[dst] = df.apply(_apply_row, axis=1)

    bases_f = ("title_token_noun", "document_token_noun", "comment_token_noun")

    def _nouns_final_row(row: pd.Series) -> list:
        """제목·본문·댓글 최종 명사를 하나의 분석용 리스트로 합친다."""
        acc: list[str] = []
        for b in bases_f:
            acc.extend(ensure_token_list(row[f"{b}{dst_suffix}"]))
        return acc

    df["nouns_final"] = df.apply(_nouns_final_row, axis=1)


def section_mean_tfidf_matrix(
    texts: list[str],
    sections: np.ndarray,
    section_ids: tuple = (1, 2, 3, 4),
    min_df: int = 2,
    max_df: float = 0.98,
) -> tuple[pd.DataFrame, object, np.ndarray]:
    """
    전체 코퍼스에 fit한 TfidfVectorizer로 동일 어휘 공간에서 섹션별 평균 TF-IDF.
    반환: (wide DataFrame index=term columns=section_1..), vectorizer, X (sparse)
    """
    from sklearn.feature_extraction.text import TfidfVectorizer

    vectorizer = TfidfVectorizer(
        min_df=min_df,
        max_df=max_df,
        token_pattern=r"(?u)\b\w+\b",
    )
    X = vectorizer.fit_transform(texts)
    terms = np.array(vectorizer.get_feature_names_out())
    sec_arr = np.asarray(sections).astype(int)

    cols = {}
    for s in section_ids:
        mask = sec_arr == s
        if not mask.any():
            cols[f"section_{s}_mean_tfidf"] = np.zeros(len(terms), dtype=float)
            continue
        sub = X[mask]
        mean_vec = np.asarray(sub.mean(axis=0)).ravel()
        cols[f"section_{s}_mean_tfidf"] = mean_vec

    wide = pd.DataFrame(cols, index=terms)
    return wide, vectorizer, X


def unique_keyword_scores(wide: pd.DataFrame, section_ids: tuple = (1, 2, 3, 4)) -> pd.DataFrame:
    """섹션 s에서의 평균 TF-IDF - 다른 섹션 평균의 최댓값."""
    out = wide.copy()
    colmap = {s: f"section_{s}_mean_tfidf" for s in section_ids}
    for s in section_ids:
        others = [colmap[k] for k in section_ids if k != s]
        own = colmap[s]
        out[f"diff_vs_others_max_s{s}"] = out[own] - out[others].max(axis=1)
    return out


def document_frequency_from_texts(texts: list[str], min_len: int = 2) -> pd.Series:
    """공백 토큰 기준 문서 내 등장 여부로 DF 카운트."""
    from collections import Counter

    df_counts = Counter()
    for doc in texts:
        toks = set(re.findall(r"\b\w+\b", doc, flags=re.UNICODE))
        for t in toks:
            if len(t) >= min_len:
                df_counts[t] += 1
    return pd.Series(df_counts, dtype=int).sort_values(ascending=False)


def sticky_candidates_within_corpus(
    texts: list[str],
    min_df: int = 2,
    max_df: float = 0.98,
    top_n: int = 200,
) -> pd.DataFrame:
    """
    단일 코퍼스(문서 문자열 리스트)만으로 TF-IDF fit.
    DF는 높은데 이 코퍼스 안에서 평균 TF-IDF는 낮은 용어 → 분기·구간 내부 고착어 후보.
    """
    from sklearn.feature_extraction.text import TfidfVectorizer

    n = len(texts)
    if n < 2:
        return pd.DataFrame()
    min_df_eff = min(max(1, min_df), max(1, n // 500 or 1))
    try:
        vectorizer = TfidfVectorizer(
            min_df=min_df_eff,
            max_df=max_df,
            token_pattern=r"(?u)\b\w+\b",
        )
        X = vectorizer.fit_transform(texts)
    except ValueError:
        return pd.DataFrame()
    terms = np.array(vectorizer.get_feature_names_out())
    if len(terms) == 0:
        return pd.DataFrame()
    mean_vec = np.asarray(X.mean(axis=0)).ravel()
    # vocabulary·정규화는 vectorizer와 동일해야 함(예: lowercase 후 토큰)
    df_c = np.asarray((X > 0).sum(axis=0)).ravel().astype(int)
    out = pd.DataFrame(
        {
            "doc_freq": df_c,
            "mean_tfidf_in_corpus": mean_vec,
        },
        index=terms,
    )
    out["sticky_score"] = out["doc_freq"] / (1.0 + out["mean_tfidf_in_corpus"] * 1000)
    return out.sort_values("sticky_score", ascending=False).head(top_n)


def sticky_candidates_per_section(
    texts: list[str],
    sections: np.ndarray,
    section_ids: tuple = (1, 2, 3, 4),
    min_df: int = 2,
    max_df: float = 0.98,
    top_n: int = 200,
) -> dict[int, pd.DataFrame]:
    """
    section 값별로 문서만 모아 코퍼스를 나눈 뒤, 각각 `sticky_candidates_within_corpus` 적용.
    통합 wide TF-IDF 고착어와 달리 «그 분기 문서들 안에서만» 상대적으로 덜 변별되는 단어를 본다.
    """
    out: dict[int, pd.DataFrame] = {}
    sec_arr = np.asarray(sections)
    for s in section_ids:
        s = int(s)
        mask = sec_arr == s
        sub = [texts[i] for i in range(len(texts)) if mask[i]]
        out[s] = sticky_candidates_within_corpus(sub, min_df=min_df, max_df=max_df, top_n=top_n)
    return out
