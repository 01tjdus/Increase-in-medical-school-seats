from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

# 프로젝트 루트 (notebooks/02_integrated/ 기준 상위 2단계)
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from project_paths import DATA_BLOG_ONLY

# 크롤 산출 CSV가 없으면 크롤 후 이 경로에 두거나, 인자로 경로를 넘깁니다.
INPUT_CSV = DATA_BLOG_ONLY / "naver_blog_medical_quota_final.csv"
OUTPUT_CSV = DATA_BLOG_ONLY / "naver_blog_medical_quota_final_jupyter.csv"
PREPARED_COLUMNS = ["title", "doc", "like", "comment_cnt", "comment_list", "ch", "date", "section"]


def read_csv_with_fallback(csv_path: str | Path) -> pd.DataFrame:
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
    return set(PREPARED_COLUMNS).issubset(df.columns)


def normalize_prepared_dataframe(raw: pd.DataFrame) -> pd.DataFrame:
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
    if pd.isna(source):
        return ""

    text = str(source).strip().lower()
    if "blog" in text or "블로그" in text:
        return "blog"
    if "cafe" in text or "카페" in text:
        return "cafe"
    return text


def build_comment_list(row: pd.Series) -> list[dict]:
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
