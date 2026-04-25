# 의대증원 중간 프로젝트 — 폴더 구조 및 작업 개요

이 문서는 **네이버 카페 크롤링**부터 **blog 데이터 통합**, **분기(section)별 불용어·TF-IDF 파이프라인**까지의 흐름과, 정리된 디렉터리 구조를 설명합니다.

---

## 디렉터리 구조

```
의대증원_중간프로젝트/
├── PROJECT_STRUCTURE.md      # 본 문서
├── project_paths.py          # ROOT, DATA_CAFE_ONLY, DATA_INTEGRATED, CONFIG_STOPWORDS, OUTPUTS_PIPELINE
├── requirements_pipeline.txt # 분기 파이프라인용 Python 패키지 목록
├── code/
│   ├── stopword_utils.py     # 불용어 필터, TF-IDF 헬퍼, 로컬 사전 적용
│   └── 의대증원_카페크롤링_v2.py  # Playwright 기반 카페 크롤러 (JSON 저장)
├── notebooks/
│   ├── cafedata_ preprocess.ipynb            # 카페 JSON → 전처리 CSV (`data/cafe_only/`)
│   ├── cafedata_total_estate_press.ipynb   # Kiwi 명사·불용어(ko) → cafe_only PKL
│   ├── make_stopwords.ipynb                # 통합 CSV 정리 → `data/integrated/` PKL
│   └── section_tfidf_stopwords_pipeline.ipynb  # 분기별 Global/Local TF-IDF·시각화
├── config/stopwords/
│   ├── stopwords-ko.txt
│   ├── stopwords_common.txt
│   └── stopwords_local_section1.txt ~ section4.txt
├── data/
│   ├── cafe_only/            # 카페 전용 크롤·전처리·PKL
│   ├── integrated/           # blog 반영 후 통합 CSV/PKL
│   └── blog_only/            # (선택) 블로그 전용 — 원격 저장소 구조와 호환
└── outputs/
    └── pipeline/
        ├── *.csv, *.png      # TF-IDF wide·고착어·워드클라우드 등 (루트에 두는 산출물)
        ├── datasets/
        ├── kmeans/
        ├── lda/
        ├── stopwords/
        ├── tfidf/
        └── wordcloud/
            ├── filtered/
            └── raw/
```

경로 상수는 [`project_paths.py`](project_paths.py)에서 `Path` 객체로 정의됩니다. 노트북은 작업 디렉터리가 `notebooks/`이거나 프로젝트 루트여도 동작하도록 `Path.cwd()`로 루트를 추정한 뒤 `project_paths`를 import합니다.

- `project_paths.py`에서 `Path` 상수, `code/` 부트스트랩(`bootstrap_code_path`), 출력 폴더 생성(`ensure_output_dirs`)을 제공합니다.
- `notebooks/section_tfidf_stopwords_pipeline.ipynb`가 분기별 불용어·TF-IDF·시각화 파이프라인의 메인 노트북입니다.
- `notebooks/cafedata_ preprocess.ipynb`, `cafedata_total_estate_press.ipynb`, `make_stopwords.ipynb`는 카페·통합 전처리 흐름용입니다.
- `config/stopwords/stopwords_local_section*.txt`는 섹션별 로컬 불용어(고착어 CSV 등을 참고해 보강)입니다.
- `outputs/pipeline/`에는 새 파이프라인 산출물(CSV·PNG)이 루트에 두어지고, kmeans/lda 등 기존 산출물은 하위 폴더에 보관될 수 있습니다.

## 데이터 흐름 (카페 → 통합 → 분기 파이프라인)

### 1) 카페 전용: 크롤링 (`code/의대증원_카페크롤링_v2.py`)

- 네이버 카페 검색 URL을 날짜 역순으로 순회하며 게시글·댓글 등을 수집합니다.
- 결과는 **`data/cafe_only/의대증원_카페_v2.json`**에 누적 저장됩니다 (`Path` 기준 프로젝트 루트).

### 2) 카페 전용: 전처리 (`notebooks/cafedata_ preprocess.ipynb`)

- 위 JSON을 읽어 DataFrame으로 정리합니다.
- 산출: **`data/cafe_only/의대증원_cafedata_preprocess.csv`**

### 3) 카페 전용: 형태소·1차 불용어 (`notebooks/cafedata_total_estate_press.ipynb`)

- 전처리 CSV 로드 후 Kiwi로 명사 추출, `config/stopwords/stopwords-ko.txt`로 제거.
- 산출 예: **`data/cafe_only/의대증원_cafedata_total_estate_press.pkl`**, POS 제거 버전 **`..._drop_list_pos.pkl`**

### 4) 통합: blog `ch` 데이터 합친 뒤 (`notebooks/make_stopwords.ipynb`)

- 협업자 쪽과 합친 **`data/integrated/combined_section_sorted.csv`**를 읽어 토큰 컬럼 등을 정리합니다.
- 산출: **`data/integrated/crolling_total_estate_press.pkl`** (블로그+카페 등 통합 분석용)

### 5) 분기별 파이프라인 (`notebooks/section_tfidf_stopwords_pipeline.ipynb` + `code/stopword_utils.py`)

- 입력: **`data/integrated/crolling_total_estate_press.pkl`**
- 레이어: `*_raw` → 공통 불용어 `*_clean` → 섹션별 로컬 `*_final` / `nouns_final`
- 사전: `config/stopwords/stopwords_common.txt` + `stopwords-ko.txt`, 섹션별 `stopwords_local_section{n}.txt`
- 산출 CSV·PNG: **`outputs/pipeline/`**
- 최종 PKL: **`data/integrated/crolling_total_estate_press_layered.pkl`**

---

## `section_tfidf_stopwords_pipeline.ipynb`와 `code/stopword_utils.py`의 차이

| 구분 | `stopword_utils.py` | `section_tfidf_stopwords_pipeline.ipynb` |
|------|---------------------|---------------------------------------------|
| **성격** | 재사용 가능한 **함수 모듈**(라이브러리) | **한 번에 끝까지 도는 분석 시나리오**(스크립트에 가까움) |
| **하는 일** | “어떻게”만 정의: 불용어 필터, raw→clean, TF-IDF 행렬·점수, 로컬 사전 적용 등 | “언제 무엇을” 실행: PKL 읽기 → 단계별로 위 함수 호출 → CSV/PNG/PKL 저장 |
| **입·출력** | DataFrame·문자열 리스트 등을 **인자로 받아 처리** (파일 저장은 하지 않음) | `project_paths`로 경로를 잡고 `data/integrated/*.pkl` 입출력, `outputs/pipeline/`에 CSV·그림 저장 |
| **시각화** | 없음 | matplotlib / seaborn / (선택) wordcloud |

**관계:** 노트북이 `from stopword_utils import ...`로 유틸을 불러와 각 셀에서 **연결**합니다. 알고리즘·지표 정의를 바꿀 때는 **`stopword_utils.py`**, 어떤 파일을 읽고 저장할지·셀 순서·그래프만 바꿀 때는 **노트북**을 수정하면 됩니다.

---

## 실행 시 유의사항

- 노트북은 **`notebooks/`에서 열고 실행**하거나, 프로젝트 루트에서 실행해도 됩니다. 첫 셀에서 `PROJECT_ROOT`를 보정합니다.
- 파이프라인 패키지: `pip install -r requirements_pipeline.txt`
- 크롤러: Playwright 등 별도 환경이 필요할 수 있습니다.

---

## 파일 역할 요약표

| 위치 | 역할 |
|------|------|
| `data/cafe_only/*` | 카페 단독 크롤·전처리·카페 단독 PKL |
| `data/integrated/*` | 통합 CSV/PKL (blog 반영 후) |
| `config/stopwords/*` | 불용어 사전 (공통·한국어·섹션 로컬) |
| `outputs/pipeline/*` | TF-IDF·빈도·시각화 산출물 |
| `code/stopword_utils.py` | 재사용 가능한 정제·TF-IDF 함수 |
