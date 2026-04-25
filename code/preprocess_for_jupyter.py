# -*- coding: utf-8 -*-
from __future__ import annotations

"""
주피터 노트북에서 바로 확인할 수 있도록 만든 전처리 모듈입니다.

이 파일은 사용자가 요청한 전처리만 수행합니다.

1. 특수문자 제거
2. 이모지 제거
3. URL 제거
4. HTML 태그 제거
5. 반복 자음 제거 ("ㅋㅋㅋ", "ㅎㅎㅎ" 같은 형태)
6. 연속 공백 제거 (띄어쓰기, 줄바꿈, 탭 포함)
7. 중복 게시글 제거
   - 전처리 후 제목이 같고
   - 본문 유사도가 0.8 이상이면
   - 먼저 나온 글만 남기고 뒤의 글을 제거

일부러 하지 않는 전처리:
- 불용어 제거
- 형태소 분석
- 띄어쓰기 교정
- 감성 라벨링
- 빈 행 제거
- 댓글 삭제

즉, 다른 팀원의 카페 데이터와 기준을 맞추기 위해
"이번에 요청된 항목만" 수행하도록 제한한 모듈입니다.
"""

import html
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd

from culumn_name_same import prepare_dataframe, read_csv_with_fallback, to_int


# 전처리된 결과를 저장할 기본 CSV 경로입니다.
# 컬럼 구조는 기존과 동일하게 유지합니다.
PREPROCESSED_OUTPUT_CSV = Path("naver_blog_medical_quota_preprocessed.csv")

# 어떤 행이 중복으로 제거되었는지 따로 확인할 수 있도록
# 중복 제거 로그도 별도 CSV로 저장합니다.
DEDUP_LOG_CSV = Path("naver_blog_medical_quota_duplicate_log.csv")

# 주피터 노트북에서 가장 자주 쓰는 기본 입력 CSV 경로입니다.
NOTEBOOK_INPUT_CSV = Path("naver_blog_medical_quota_final_jupyter.csv")


# URL 제거용 정규식입니다.
# http://..., https://..., www.... 형태를 모두 공백으로 치환합니다.
URL_PATTERN = re.compile(r"(https?://\S+|www\.\S+)")

# HTML 태그 제거용 정규식입니다.
# <div>, <br>, <p> 같은 태그를 공백으로 바꿉니다.
HTML_TAG_PATTERN = re.compile(r"<[^>]+>")

# 이모지 제거용 정규식입니다.
# 모바일 환경에서 자주 쓰이는 범위를 넓게 잡아서 먼저 제거합니다.
EMOJI_PATTERN = re.compile(
    "["
    "\U0001F300-\U0001F6FF"
    "\U0001F900-\U0001FAFF"
    "\u2600-\u26FF"
    "\u2700-\u27BF"
    "\uFE0F"
    "\u200D"
    "]+",
    flags=re.UNICODE,
)

# 연속 공백 정리용 정규식입니다.
# 여러 칸 띄어쓰기뿐 아니라 \n, \t 도 모두 한 칸 공백으로 정리합니다.
WHITESPACE_PATTERN = re.compile(r"\s+")

HANGUL_START = 0xAC00
HANGUL_END = 0xD7A3
LAUGH_CHAR_CODES = {0x314B, 0x314E}


def emit_progress(message: str, verbose: bool = False) -> None:
    """노트북 셀 출력에서 진행 상황이 바로 보이도록 합니다."""
    if verbose:
        print(message, flush=True)


def ensure_parent_dir(path: str | Path) -> Path:
    """저장 경로의 부모 디렉터리가 없으면 미리 생성합니다."""
    resolved_path = Path(path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    return resolved_path


def describe_input_source(data: str | Path | pd.DataFrame) -> str:
    """진행 메시지에 표시할 입력 데이터 설명을 만듭니다."""
    if isinstance(data, pd.DataFrame):
        return "in-memory DataFrame"
    return str(Path(data))


def remove_repeated_laughs(text: str) -> str:
    """ㅋㅋㅋ, ㅎㅎㅎ처럼 반복된 자음 덩어리를 공백으로 치환합니다."""
    result: list[str] = []
    index = 0

    while index < len(text):
        code_point = ord(text[index])
        if code_point in LAUGH_CHAR_CODES:
            end = index + 1
            while end < len(text) and text[end] == text[index]:
                end += 1
            if end - index >= 2:
                result.append(" ")
                index = end
                continue

        result.append(text[index])
        index += 1

    return "".join(result)


def keep_allowed_text_characters(text: str) -> str:
    """한글, 영문, 숫자, 공백만 남기고 나머지는 공백으로 바꿉니다."""

    def is_allowed(char: str) -> bool:
        code_point = ord(char)
        return (
            char.isascii() and (char.isalnum() or char.isspace())
        ) or (HANGUL_START <= code_point <= HANGUL_END) or char.isspace()

    return "".join(char if is_allowed(char) else " " for char in text)


def parse_comment_list(value) -> list[dict]:
    """
    comment_list 컬럼을 항상 list[dict] 형태로 맞춥니다.

    왜 필요한가:
    - CSV에서 읽으면 comment_list는 보통 JSON 문자열입니다.
    - 노트북에서 다루기 쉽게 하려면 실제 파이썬 리스트 형태가 필요합니다.
    - 이미 리스트로 들어온 경우도 있으므로 둘 다 처리합니다.
    """
    if isinstance(value, list):
        return value

    if pd.isna(value) or not str(value).strip():
        return []

    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError:
        return []

    return parsed if isinstance(parsed, list) else []


def clean_noise_text(value) -> str:
    """
    사용자가 요청한 노이즈 제거만 적용합니다.

    처리 순서:
    1. HTML 엔티티 해제
    2. HTML 태그 제거
    3. URL 제거
    4. 반복 자음 제거
    5. 이모지 제거
    6. 특수문자 제거
    7. 연속 공백 정리

    주의:
    - 이 함수는 형태소 분석이나 불용어 제거를 하지 않습니다.
    - 이번 요청 범위에 포함된 정리만 수행합니다.
    """
    if pd.isna(value):
        return ""

    text = html.unescape(str(value))
    text = HTML_TAG_PATTERN.sub(" ", text)
    text = URL_PATTERN.sub(" ", text)
    text = remove_repeated_laughs(text)
    text = EMOJI_PATTERN.sub(" ", text)
    text = keep_allowed_text_characters(text)
    text = WHITESPACE_PATTERN.sub(" ", text)
    return text.strip()


def clean_comment_list(comment_list) -> list[dict]:
    """
    comment_list 안의 comment_content 텍스트만 정리합니다.

    구조는 그대로 유지합니다.
    {
        "comment_content": ...,
        "comment_like": ...,
        "comment_date": ...
    }

    이렇게 하는 이유:
    - 팀원 데이터와 컬럼 구조를 맞춰야 하기 때문입니다.
    - 이번 요청은 노이즈 제거이지 스키마 변경이 아닙니다.
    """
    cleaned_comments = []

    for item in parse_comment_list(comment_list):
        cleaned_comments.append(
            {
                "comment_content": clean_noise_text(item.get("comment_content", "")),
                "comment_like": to_int(item.get("comment_like", 0)),
                "comment_date": str(item.get("comment_date", "") or "").strip(),
            }
        )

    return cleaned_comments


def load_prepared_dataframe(csv_path: str | Path) -> pd.DataFrame:
    """
    공유 스키마에 맞는 데이터프레임으로 읽어옵니다.

    culumn_name_same.py의 prepare_dataframe을 사용하기 때문에
    아래 두 경우를 모두 처리할 수 있습니다.
    - 원본 final.csv
    - 이미 컬럼명이 맞춰진 *_jupyter.csv
    """
    return prepare_dataframe(csv_path)


def apply_requested_cleaning(df: pd.DataFrame, verbose: bool = False) -> pd.DataFrame:
    """
    요청된 전처리를 title, doc, comment_list에만 적용합니다.

    변경하는 컬럼:
    - title
    - doc
    - comment_list 내부 comment_content

    변경하지 않는 컬럼:
    - like
    - comment_cnt
    - ch
    - date
    - section
    """
    cleaned = df.copy(deep=True)
    emit_progress("    - title 정제 중...", verbose)
    cleaned["title"] = cleaned["title"].fillna("").apply(clean_noise_text)
    emit_progress("    - doc 정제 중...", verbose)
    cleaned["doc"] = cleaned["doc"].fillna("").apply(clean_noise_text)
    emit_progress("    - comment_list 정제 중...", verbose)
    cleaned["comment_list"] = cleaned["comment_list"].apply(clean_comment_list)
    return cleaned


def doc_similarity(left: str, right: str) -> float:
    """
    두 본문의 유사도를 계산합니다.

    사용 이유:
    - 사용자가 "본문 80% 이상 일치" 기준을 원했기 때문입니다.
    - 외부 라이브러리를 추가하지 않고 바로 쓸 수 있는 SequenceMatcher를 사용합니다.
    """
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def drop_similar_duplicates(
    df: pd.DataFrame,
    similarity_threshold: float = 0.8,
    verbose: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    요청된 규칙으로 중복 게시글을 제거합니다.

    규칙:
    - 전처리 후 제목이 같은 행끼리만 비교
    - 같은 제목 그룹 안에서 본문 유사도가 threshold 이상이면
      먼저 나온 행만 남기고 뒤의 행을 제거

    제목 기준으로 먼저 묶는 이유:
    - 사용자가 "동일 제목 + 본문 80% 이상 일치"라고 기준을 줬기 때문입니다.
    - 전체 행을 전부 서로 비교하면 너무 느려지므로 제목 그룹 안에서만 비교합니다.
    """
    keep_indices: list[int] = []
    duplicate_records: list[dict] = []
    total_groups = int(df["title"].nunique(dropna=False))
    next_progress_percent = 10

    # groupby(sort=False)로 두면 원래 등장 순서를 최대한 유지할 수 있습니다.
    for group_number, (_, group) in enumerate(
        df.groupby("title", sort=False, dropna=False),
        start=1,
    ):
        kept_in_group: list[int] = []

        for idx in group.index:
            current_doc = str(df.at[idx, "doc"] or "")
            matched_idx = None
            matched_ratio = 0.0

            # 같은 제목 그룹 안에서 이미 남겨둔 글과만 비교합니다.
            for kept_idx in kept_in_group:
                ratio = doc_similarity(current_doc, str(df.at[kept_idx, "doc"] or ""))
                if ratio >= similarity_threshold:
                    matched_idx = kept_idx
                    matched_ratio = ratio
                    break

            # 중복이 아니면 유지 대상에 추가합니다.
            if matched_idx is None:
                kept_in_group.append(idx)
                keep_indices.append(idx)
                continue

            # 중복이면 어떤 행이 어떤 행 때문에 제거됐는지 로그에 남깁니다.
            duplicate_records.append(
                {
                    "removed_index": idx,
                    "kept_index": matched_idx,
                    "title": df.at[idx, "title"],
                    "similarity": round(matched_ratio, 4),
                    "date": df.at[idx, "date"],
                    "section": df.at[idx, "section"],
                }
            )

        progress_percent = int(group_number * 100 / total_groups) if total_groups else 100
        if verbose and (
            group_number == total_groups or progress_percent >= next_progress_percent
        ):
            emit_progress(
                "    - 중복 검사 진행 "
                f"{group_number:,}/{total_groups:,} 제목 그룹 ({progress_percent}%), "
                f"현재 제거 {len(duplicate_records):,}건",
                verbose,
            )
            while next_progress_percent <= progress_percent:
                next_progress_percent += 10

    deduped = df.loc[keep_indices].reset_index(drop=True)
    duplicate_log = pd.DataFrame(duplicate_records)
    return deduped, duplicate_log


def build_preprocessing_report(
    original_df: pd.DataFrame,
    cleaned_df: pd.DataFrame,
    deduped_df: pd.DataFrame,
    duplicate_log: pd.DataFrame,
) -> pd.DataFrame:
    """
    주피터에서 바로 볼 수 있는 요약 표를 만듭니다.

    이 표로 빠르게 확인할 수 있는 것:
    - 총 몇 건이 있었는지
    - 중복이 몇 건 제거됐는지
    - 제목/본문/댓글에 실제 변경이 얼마나 있었는지
    """

    def comment_content_changed_count() -> int:
        """
        댓글 내용이 실제로 바뀐 행 수를 계산합니다.

        like/date는 이번 전처리 대상이 아니므로 비교하지 않고,
        comment_content 텍스트만 비교합니다.
        """
        changed = 0
        before_lists = original_df["comment_list"].apply(parse_comment_list)
        after_lists = cleaned_df["comment_list"].apply(parse_comment_list)

        for before_comments, after_comments in zip(before_lists, after_lists):
            before_texts = [str(item.get("comment_content", "")) for item in before_comments]
            after_texts = [str(item.get("comment_content", "")) for item in after_comments]
            if before_texts != after_texts:
                changed += 1

        return changed

    return pd.DataFrame(
        {
            "항목": [
                "전처리 전 게시글 수",
                "전처리 후 게시글 수",
                "중복 제거 게시글 수",
                "제목 정제 변경 행 수",
                "본문 정제 변경 행 수",
                "댓글 정제 변경 행 수",
            ],
            "값": [
                len(original_df),
                len(deduped_df),
                len(duplicate_log),
                int((original_df["title"].fillna("") != cleaned_df["title"].fillna("")).sum()),
                int((original_df["doc"].fillna("") != cleaned_df["doc"].fillna("")).sum()),
                comment_content_changed_count(),
            ],
        }
    )


def build_change_preview(
    original_df: pd.DataFrame,
    cleaned_df: pd.DataFrame,
    rows: int = 10,
) -> pd.DataFrame:
    """
    전처리 전/후를 눈으로 비교할 수 있는 미리보기 표를 만듭니다.

    전체 CSV를 직접 열지 않아도,
    어떤 식으로 문자열이 바뀌는지 바로 확인할 수 있도록 만든 표입니다.
    """
    before_comment_lists = original_df["comment_list"].apply(parse_comment_list)
    after_comment_lists = cleaned_df["comment_list"].apply(parse_comment_list)

    preview = pd.DataFrame(
        {
            "title_before": original_df["title"],
            "title_after": cleaned_df["title"],
            "doc_before": original_df["doc"],
            "doc_after": cleaned_df["doc"],
            # 표가 너무 넓어지지 않도록 첫 번째 댓글만 샘플로 보여줍니다.
            "comment_before": before_comment_lists.apply(
                lambda items: items[0].get("comment_content", "") if items else ""
            ),
            "comment_after": after_comment_lists.apply(
                lambda items: items[0].get("comment_content", "") if items else ""
            ),
        }
    )

    changed_mask = (
        (preview["title_before"] != preview["title_after"])
        | (preview["doc_before"] != preview["doc_after"])
        | (preview["comment_before"] != preview["comment_after"])
    )

    return preview.loc[changed_mask].head(rows).reset_index(drop=True)


def preprocess_dataframe(
    data: str | Path | pd.DataFrame,
    similarity_threshold: float = 0.8,
    verbose: bool = False,
    preview_rows: int = 10,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    주피터에서 쓰기 위한 메인 진입 함수입니다.

    반환값:
    1. 전처리 + 중복 제거가 끝난 데이터프레임
    2. 요약 리포트 데이터프레임
    3. 중복 제거 로그 데이터프레임
    4. 전처리 전/후 미리보기 데이터프레임

    입력 가능 형태:
    - final.csv 경로
    - *_jupyter.csv 경로
    - 이미 불러온 DataFrame
    """
    emit_progress(
        f"[1/4] 입력 데이터 불러오는 중... ({describe_input_source(data)})",
        verbose,
    )

    if isinstance(data, pd.DataFrame):
        original_df = data.copy(deep=True)
        original_df["comment_list"] = original_df["comment_list"].apply(parse_comment_list)
    else:
        original_df = load_prepared_dataframe(data)

    emit_progress(f"      불러오기 완료: {len(original_df):,}건", verbose)
    emit_progress("[2/4] 텍스트와 댓글 노이즈를 정제하는 중...", verbose)
    cleaned_df = apply_requested_cleaning(original_df, verbose=verbose)
    emit_progress("[3/4] 유사 중복 게시글을 검사하는 중...", verbose)
    deduped_df, duplicate_log = drop_similar_duplicates(
        cleaned_df,
        similarity_threshold=similarity_threshold,
        verbose=verbose,
    )
    emit_progress("[4/4] 요약 리포트와 미리보기를 만드는 중...", verbose)
    report_df = build_preprocessing_report(original_df, cleaned_df, deduped_df, duplicate_log)
    preview_df = build_change_preview(original_df, cleaned_df, rows=preview_rows)
    emit_progress(
        f"      전처리 완료: {len(deduped_df):,}건 유지, 중복 {len(duplicate_log):,}건 제거",
        verbose,
    )
    return deduped_df, report_df, duplicate_log, preview_df


def save_preprocessed_csv(
    input_csv: str | Path | pd.DataFrame = NOTEBOOK_INPUT_CSV,
    output_csv: str | Path = PREPROCESSED_OUTPUT_CSV,
    duplicate_log_csv: str | Path = DEDUP_LOG_CSV,
    similarity_threshold: float = 0.8,
    verbose: bool = False,
    preview_rows: int = 10,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    전처리를 수행한 뒤 결과를 CSV로 저장합니다.

    저장되는 파일:
    - 전처리 완료 CSV
    - 중복 제거 로그 CSV

    저장된 CSV도 기존 공유 스키마를 유지하므로
    이후 주피터 노트북에서 그대로 다시 불러올 수 있습니다.
    """
    emit_progress("[0/5] 주피터용 전처리와 저장을 시작합니다.", verbose)

    deduped_df, report_df, duplicate_log, preview_df = preprocess_dataframe(
        input_csv,
        similarity_threshold=similarity_threshold,
        verbose=verbose,
        preview_rows=preview_rows,
    )

    output_frame = deduped_df.copy()
    output_frame["comment_list"] = output_frame["comment_list"].apply(
        lambda value: json.dumps(value, ensure_ascii=False)
    )

    output_path = ensure_parent_dir(output_csv)
    duplicate_log_path = ensure_parent_dir(duplicate_log_csv)

    emit_progress("[5/5] 전처리 결과와 중복 로그를 CSV로 저장하는 중...", verbose)
    output_frame.to_csv(output_path, index=False, encoding="utf-8-sig")
    duplicate_log.to_csv(duplicate_log_path, index=False, encoding="utf-8-sig")
    emit_progress(f"      전처리 CSV 저장 완료: {output_path.resolve()}", verbose)
    emit_progress(f"      중복 로그 저장 완료: {duplicate_log_path.resolve()}", verbose)
    return deduped_df, report_df, duplicate_log, preview_df


def load_saved_preprocessing_results(
    output_csv: str | Path = PREPROCESSED_OUTPUT_CSV,
    duplicate_log_csv: str | Path = DEDUP_LOG_CSV,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    저장된 전처리 결과와 중복 로그를 노트북에서 다시 확인할 때 사용합니다.
    """
    saved_df = load_prepared_dataframe(output_csv)
    duplicate_log_df = read_csv_with_fallback(duplicate_log_csv)
    return saved_df, duplicate_log_df


def run_preprocessing_notebook(
    input_csv: str | Path | pd.DataFrame = NOTEBOOK_INPUT_CSV,
    output_csv: str | Path = PREPROCESSED_OUTPUT_CSV,
    duplicate_log_csv: str | Path = DEDUP_LOG_CSV,
    similarity_threshold: float = 0.8,
    preview_rows: int = 10,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    주피터 노트북에서 바로 실행하기 좋은 래퍼 함수입니다.

    단계별 진행 상황을 출력하고, 결과 CSV와 중복 로그 CSV까지 저장합니다.
    """
    return save_preprocessed_csv(
        input_csv=input_csv,
        output_csv=output_csv,
        duplicate_log_csv=duplicate_log_csv,
        similarity_threshold=similarity_threshold,
        verbose=True,
        preview_rows=preview_rows,
    )


# %%
# 주피터 / VS Code 노트북 예시 1
# 전처리 결과, 요약 표, 미리보기 표, 중복 로그를 한 번에 확인하는 셀입니다.
#
# from IPython.display import display
# from preprocess_for_jupyter import preprocess_dataframe
#
# preprocessed_df, report_df, duplicate_log_df, preview_df = preprocess_dataframe(
#     "naver_blog_medical_quota_final_jupyter.csv",
#     verbose=True,
# )
#
# display(report_df)
# display(preview_df)
# display(preprocessed_df[["title", "like", "comment_cnt", "ch", "date", "section"]].head(10))
# display(duplicate_log_df.head(10))


# %%
# 주피터 / VS Code 노트북 예시 2
# comment_list 안을 표처럼 보고 싶을 때 쓰는 셀입니다.
#
# comment_preview_df = pd.DataFrame(preprocessed_df.loc[0, "comment_list"])
# display(comment_preview_df.head(20))


# %%
# 주피터 / VS Code 노트북 예시 3
# 전처리 결과를 CSV로 저장하고 싶을 때 쓰는 셀입니다.
#
# from preprocess_for_jupyter import run_preprocessing_notebook
#
# preprocessed_df, report_df, duplicate_log_df, preview_df = run_preprocessing_notebook()
# display(report_df)


# %%
# 주피터 / VS Code 노트북 예시 4
# 저장된 결과만 다시 불러와서 확인하고 싶을 때 쓰는 셀입니다.
#
# from IPython.display import display
# from preprocess_for_jupyter import load_saved_preprocessing_results
#
# saved_df, saved_duplicate_log_df = load_saved_preprocessing_results()
# display(saved_df[["title", "like", "comment_cnt", "ch", "date", "section"]].head(10))
# display(saved_duplicate_log_df.head(10))


if __name__ == "__main__":
    preprocessed_df, report_df, duplicate_log_df, preview_df = run_preprocessing_notebook()
    print(f"saved rows: {len(preprocessed_df):,}")
    print(f"duplicates removed: {len(duplicate_log_df):,}")
    print(f"saved file: {PREPROCESSED_OUTPUT_CSV}")
