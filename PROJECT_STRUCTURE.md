## 디렉터리 구조

```text
의대증원_중간프로젝트/
├── PROJECT_STRUCTURE.md
├── project_paths.py
├── requirements_pipeline.txt
├── code/
│   ├── stopword_utils.py
│   ├── 의대증원_카페크롤링_v2.py
│   ├── culumn_name_same.py
│   ├── preprocess_for_jupyter.py
│   └── naver_crawler.py
├── notebooks/
│   ├── cafedata_preprocess.ipynb
│   ├── cafedata_total_estate_press.ipynb
│   ├── make_stopwords.ipynb
│   ├── preprocess_after_project.ipynb
│   └── section_tfidf_stopwords_pipeline.ipynb
├── config/
│   └── stopwords/
│       ├── stopwords-ko.txt
│       ├── stopwords_common.txt
│       ├── stopwords_local_section1.txt
│       ├── stopwords_local_section2.txt
│       ├── stopwords_local_section3.txt
│       └── stopwords_local_section4.txt
├── data/
│   ├── blog_only/
│   └── integrated/
└── outputs/
    └── pipeline/
        ├── datasets/
        ├── kmeans/
        ├── lda/
        ├── stopwords/
        ├── tfidf/
        └── wordcloud/
            ├── filtered/
            └── raw/
```

## 메모

- `project_paths.py`에서 `Path` 상수, `code/` 부트스트랩 함수, 출력 폴더 생성 함수를 제공합니다.
- `notebooks/preprocess_after_project.ipynb`는 전처리 이후 분석을 4구간 기준으로 순서대로 실행하는 메인 노트북입니다.
- `notebooks/section_tfidf_stopwords_pipeline.ipynb`는 기존 분석 노트북을 구조에 맞춘 위치로 연결한 파일입니다.
- `cafedata_preprocess.ipynb`, `cafedata_total_estate_press.ipynb`, `make_stopwords.ipynb`는 현재 플레이스홀더입니다.
- `config/stopwords/stopwords_local_section*.txt`는 현재 계산된 구간별 자동 불용어에서 생성했습니다.
- `outputs/pipeline/` 아래 결과물은 유형별 하위 폴더로 나누어 저장합니다.
- 기존 루트 파일 일부는 호환성과 안전한 전환을 위해 남아 있을 수 있습니다.

## 4구간 분석 흐름

`notebooks/preprocess_after_project.ipynb`에서는 아래 순서로 분석을 진행합니다.

1. 전처리된 파일 불러오기
   - 입력 파일: `data/integrated/combined_section_sorted_flat_comments.pkl`
   - 기준 컬럼: `section` 1~4구간, `title_token_noun`, `document_token_noun`, `comment_token_noun`
2. 불용어 처리 전 워드클라우드
   - 전체 1장이 아니라 `section`별 4개 워드클라우드를 생성합니다.
3. 불용어 적용
   - 불용어 파일: `config/stopwords/analysis_stopwords_excluded.txt`
   - 적용 컬럼: `full_nouns_filtered`
4. 불용어 처리 후 워드클라우드
   - 전체 1장이 아니라 `section`별 4개 워드클라우드를 생성합니다.
5. TF-IDF
   - 문서 단위 전체 평균이 아니라 `section_df` 기준 4구간 비교용 TF-IDF를 계산합니다.
6. K-means
   - 전체 문서를 한 번에 군집화하지 않고, 각 구간 안의 개별 문서들에 대해 따로 수행합니다.
7. LDA 토픽 모델링
   - 전체 문서를 한 번에 토픽 모델링하지 않고, 각 구간 안의 개별 문서들에 대해 따로 수행합니다.

## 분석 기준 정리

- 워드클라우드: `section`별 4개
- TF-IDF: `section_df` 기준 4구간 비교
- K-means: 각 구간 안에서 따로
- LDA: 각 구간 안에서 따로

## K-means의 K 결정 기준

- 엘보우 기법은 전체 문서 한 번이 아니라 `section`별 문서 집합에 대해 각각 수행합니다.
- 입력 행렬은 각 구간의 `doc_text_filtered`를 TF-IDF로 벡터화한 결과를 사용합니다.
- 탐색 범위는 보통 `K=2 ~ K=8`로 두고, 문서 수나 단어 수가 부족하면 가능한 최대 범위까지만 계산합니다.
- 선택 기준은 다음과 같습니다.
  - `K`가 증가할수록 SSE는 항상 감소하므로, 단순히 SSE가 가장 작은 값을 고르지 않습니다.
  - SSE 감소폭이 급격하다가 완만해지는 첫 번째 꺾이는 지점을 우선 후보로 봅니다.
  - 해석 가능성과 구간 간 비교 가능성을 위해, 필요 이상으로 큰 `K`는 피합니다.
- 현재 데이터에서는 대부분의 구간에서 `K=2 -> 3`으로 갈 때 SSE 감소폭이 가장 크고, 그 이후부터는 감소폭이 비교적 완만해집니다.
- 따라서 본 프로젝트의 기본 분석에서는 `K=3`을 공통 기준으로 사용하고, 필요할 경우 해석이 부족한 구간에 한해 `K=4`를 보조 비교값으로 검토합니다.
