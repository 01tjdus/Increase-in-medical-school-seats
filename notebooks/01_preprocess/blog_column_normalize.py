"""블로그 CSV를 01 전처리용 표준 컬럼으로 맞추는 보조 스크립트.

블로그 수집 결과는 실행 시점이나 협업 파일 형식에 따라 컬럼명이 조금씩
다를 수 있다. 이 파일은 제목, 본문, 좋아요, 댓글, 채널, 날짜, 구간을
`PREPARED_COLUMNS` 순서로 정리한다. 최종 기준 전처리는
`blog_preprocess.ipynb`에서 명사 토큰화까지 수행한다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

# 프로젝트 루트 (notebooks/01_preprocess/ 기준 상위 2단계)
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from project_paths import DATA_BLOG_ONLY

# 블로그 전처리에서 찾는 순서: 이미 정규화된 파일 → 협업용 최종 → 크롤 원본
BLOG_CSV_CANDIDATES = (
    "naver_blog_medical_quota_final_jupyter.csv",
    "naver_blog_medical_quota_preprocessed.csv",
    "naver_blog_medical_quota_final.csv",
    "naver_blog_medical_quota.csv",
)


def resolve_existing_blog_csv() -> Path:
    """data/blog_only 안에서 실제로 있는 블로그 CSV 하나를 고릅니다."""
    for name in BLOG_CSV_CANDIDATES:
        p = DATA_BLOG_ONLY / name
        if p.is_file():
            return p
    raise FileNotFoundError(
        "data/blog_only/에 블로그 CSV가 없습니다. 다음 중 하나를 두세요: "
        + ", ".join(BLOG_CSV_CANDIDATES)
    )


def _default_input_csv() -> Path:
    """save_prepared_csv / prepare_dataframe 기본 입력. 협업용 final → 전처리본 → 크롤 원본 순."""
    for name in (
        "naver_blog_medical_quota_final.csv",
        "naver_blog_medical_quota_preprocessed.csv",
        "naver_blog_medical_quota.csv",
    ):
        p = DATA_BLOG_ONLY / name
        if p.is_file():
            return p
    return DATA_BLOG_ONLY / "naver_blog_medical_quota_final.csv"


# 크롤 산출 CSV가 없으면 크롤 후 이 경로에 두거나, 인자로 경로를 넘깁니다.
INPUT_CSV = _default_input_csv()
OUTPUT_CSV = DATA_BLOG_ONLY / "naver_blog_medical_quota_final_jupyter.csv"
PREPARED_COLUMNS = ["title", "doc", "like", "comment_cnt", "comment_list", "ch", "date", "section"]


def read_csv_with_fallback(csv_path: str | Path) -> pd.DataFrame:
    """UTF-8과 국내 CSV에서 자주 쓰이는 인코딩을 차례로 시도해 파일을 읽는다."""
    encodings = ["utf-8-sig", "utf-8", "cp949", "euc-kr"]
    last_error = None

    for encoding in encodings:
        try:
            return pd.read_csv(csv_path, low_memory=False, encoding=encoding)
        except UnicodeDecodeError as exc:
            last_error = exc

    if last_error is not None:
        raise last_error
    raise ValueError(f"failed to read csv: {csv_path}")


def to_int(value, default: int = 0) -> int:
    """쉼표, 공백, 단위 문자가 섞인 숫자 문자열을 정수로 바꾼다."""
    if pd.isna(value):
        return default
    text = str(value).strip()
    if not text:
        return default
    text = text.replace(",", "")
    if text.endswith(".0"):
        text = text[:-2]
    try:
        return int(text)
    except ValueError:
        digits = "".join(ch for ch in text if ch.isdigit())
        return int(digits) if digits else default


def normalize_date(value) -> str:
    """여러 날짜 표기를 YYYY-MM-DD 문자열로 통일한다."""
    if pd.isna(value):
        return ""

    text = str(value).strip()
    if not text:
        return ""
    if text.endswith(".0"):
        text = text[:-2]

    parsed = pd.to_datetime(text, format="%Y%m%d", errors="coerce")
    if pd.isna(parsed):
        parsed = pd.to_datetime(text, errors="coerce")

    return parsed.strftime("%Y-%m-%d") if not pd.isna(parsed) else ""


def normalize_section(value, date_value="") -> int:
    """명시된 section이 없을 때 날짜를 기준으로 1~4구간을 부여한다."""
    section = to_int(value, default=0)
    if section in {1, 2, 3, 4}:
        return section

    normalized_date = normalize_date(date_value)
    if not normalized_date:
        return 0

    if "2024-01-01" <= normalized_date <= "2024-03-31":
        return 1
    if "2024-04-01" <= normalized_date <= "2024-06-30":
        return 2
    if "2024-07-01" <= normalized_date <= "2024-12-31":
        return 3
    if "2025-01-01" <= normalized_date <= "2025-06-30":
        return 4
    return 0


def is_prepared_dataframe(df: pd.DataFrame) -> bool:
    """이미 통합용 표준 컬럼을 갖춘 파일인지 확인한다."""
    return set(PREPARED_COLUMNS).issubset(df.columns)


def normalize_prepared_dataframe(raw: pd.DataFrame) -> pd.DataFrame:
    """표준 컬럼 파일을 다시 읽을 때 타입과 댓글 JSON만 정리한다."""
    prepared = raw.copy()

    for column in ["title", "doc", "ch", "date"]:
        prepared[column] = prepared[column].fillna("").astype(str)

    prepared["like"] = prepared["like"].apply(to_int)
    prepared["comment_cnt"] = prepared["comment_cnt"].apply(to_int)
    prepared["section"] = prepared.apply(
        lambda row: normalize_section(row.get("section", ""), row.get("date", "")),
        axis=1,
    )

    def normalize_comment_list(value):
        if isinstance(value, list):
            parsed = value
        elif pd.isna(value) or not str(value).strip():
            parsed = []
        else:
            try:
                parsed = json.loads(str(value))
            except json.JSONDecodeError:
                parsed = []

        normalized = []
        for item in parsed:
            normalized.append(
                {
                    "comment_content": str(item.get("comment_content", "")).strip(),
                    "comment_like": to_int(item.get("comment_like", 0)),
                    "comment_date": normalize_date(item.get("comment_date", "")),
                }
            )
        return normalized

    prepared["comment_list"] = prepared["comment_list"].apply(normalize_comment_list)
    prepared = prepared[PREPARED_COLUMNS]
    prepared = prepared[prepared["section"].isin([1, 2, 3, 4])].reset_index(drop=True)
    return prepared


def map_channel(source) -> str:
    """원본 source 값을 blog/cafe 등 분석용 채널명으로 단순화한다."""
    if pd.isna(source):
        return ""

    text = str(source).strip().lower()
    if "blog" in text or "블로그" in text:
        return "blog"
    if "cafe" in text or "카페" in text:
        return "cafe"
    return text


def build_comment_list(row: pd.Series) -> list[dict]:
    """분리 저장된 댓글 텍스트·날짜·좋아요를 list[dict] 구조로 묶는다."""
    comments = []
    raw_json = row.get("comments_json", "")

    if isinstance(raw_json, str) and raw_json.strip():
        try:
            parsed = json.loads(raw_json)
        except json.JSONDecodeError:
            parsed = []

        for item in parsed:
            comments.append(
                {
                    "comment_content": str(item.get("text", "")).strip(),
                    "comment_like": to_int(item.get("like_count", 0)),
                    "comment_date": normalize_date(item.get("time", "")),
                }
            )
        return comments

    texts = [part.strip() for part in str(row.get("comments_text", "")).split(" || ") if part.strip()]
    times = [part.strip() for part in str(row.get("comment_times", "")).split(" || ") if part.strip()]
    likes = [part.strip() for part in str(row.get("comment_like_counts", "")).split(" || ") if part.strip()]

    max_len = max(len(texts), len(times), len(likes))
    for idx in range(max_len):
        comments.append(
            {
                "comment_content": texts[idx] if idx < len(texts) else "",
                "comment_like": to_int(likes[idx], default=0) if idx < len(likes) else 0,
                "comment_date": normalize_date(times[idx]) if idx < len(times) else "",
            }
        )
    return comments


def prepare_dataframe(csv_path: str | Path = INPUT_CSV) -> pd.DataFrame:
    """원본 또는 표준화된 블로그 CSV를 통합 분석용 DataFrame으로 변환한다."""
    raw = read_csv_with_fallback(csv_path)

    if is_prepared_dataframe(raw):
        return normalize_prepared_dataframe(raw)

    like_series = raw["post_like_count"] if "post_like_count" in raw.columns else raw["like_count"]
    date_series = raw["date"] if "date" in raw.columns else raw["post_date"]
    section_series = (
        raw.apply(
            lambda row: normalize_section(
                row.get("section", ""),
                row.get("date", row.get("post_date", "")),
            ),
            axis=1,
        )
        if "section" in raw.columns or "date" in raw.columns or "post_date" in raw.columns
        else 0
    )

    prepared = pd.DataFrame(
        {
            "title": raw["title"].fillna(""),
            "doc": raw["content"].fillna(""),
            "like": like_series.apply(to_int),
            "comment_cnt": raw["comment_count"].apply(to_int),
            "comment_list": raw.apply(build_comment_list, axis=1),
            "ch": raw["source"].apply(map_channel),
            "date": date_series.apply(normalize_date),
            "section": section_series,
        }
    )

    prepared = prepared[prepared["section"].isin([1, 2, 3, 4])].reset_index(drop=True)
    return prepared


def save_prepared_csv(
    input_csv: str | Path = INPUT_CSV,
    output_csv: str | Path = OUTPUT_CSV,
) -> pd.DataFrame:
    """정리된 블로그 표를 CSV로 저장하고, 메모리에서는 댓글 리스트 구조를 유지한다."""
    prepared = prepare_dataframe(input_csv)
    output_frame = prepared.copy()
    output_frame["comment_list"] = output_frame["comment_list"].apply(
        lambda value: json.dumps(value, ensure_ascii=False)
    )
    out_path = Path(output_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    output_frame.to_csv(out_path, index=False, encoding="utf-8-sig")
    return prepared


# %%
# Jupyter / VS Code notebook-style example:
# df = prepare_dataframe(INPUT_CSV)
# df.head()


# %%
# df[["title", "like", "comment_cnt", "ch", "date", "section"]].head()


# %%
# df.loc[0, "comment_list"][:2]


if __name__ == "__main__":
    prepared_df = save_prepared_csv()
    print(f"saved rows: {len(prepared_df):,}")
    print(f"saved file: {Path(OUTPUT_CSV).resolve()}")
