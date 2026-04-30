# `data/blog_only/` — 블로그 전용

블로그만 따로 받거나, **이 저장소의 블로그 크롤러**로 직접 쌓은 파일을 두는 폴더입니다.


| 파일명                                          | 의미                          | 생성                                                                                               | 다음 단계                                                                                                                    |
| -------------------------------------------- | --------------------------- | ------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------ |
| `naver_blog_medical_quota.csv`               | 검색·기간별로 모은 블로그 글 본문·댓글 등    | `[notebooks/00_crolling/blog_crolling.py](../../notebooks/00_crolling/blog_crolling.py)` (기본 출력) | 통합 단계에서 `combined_section_sorted.csv` 등과 합쳐 `data/integrated/`로                                                          |
| `naver_blog_medical_quota_links.csv`         | 수집 링크 체크포인트                 | `blog_crolling.py`                                                                               | 크롤 재시작 시 이어 받기                                                                                                           |
| `naver_blog_medical_quota_final.csv`         | 최종 블로그 CSV                  | 외부 전달 또는 후처리                                                                                     | `[notebooks/01_preprocess/blog_preprocess.ipynb](../../notebooks/01_preprocess/blog_preprocess.ipynb)`                   |
| `naver_blog_medical_quota_final_jupyter.csv` | 컬럼명·댓글 리스트 정규화 결과           | `blog_column_normalize.py`                                                                       | `blog_preprocess.ipynb` 입력 후보                                                                                            |
| `naver_blog_medical_quota_preprocessed.csv`  | 블로그 표준 컬럼·명사 토큰 CSV         | `blog_preprocess.ipynb`                                                                          | `[notebooks/02_integrated/integrated_preprocessing.ipynb](../../notebooks/02_integrated/integrated_preprocessing.ipynb)` |
| `naver_blog_medical_quota_preprocessed.pkl`  | 리스트 컬럼을 객체로 보존한 블로그 전처리 PKL | `blog_preprocess.ipynb`                                                                          | `integrated_preprocessing.ipynb` 우선 입력                                                                                   |


`blog_crolling.py`는 `--output`, `--links-output`으로 경로를 바꿀 수 있습니다. 기본값은 **항상 이 폴더**(저장소 루트 기준)입니다.

- 경로 상수: `[project_paths.DATA_BLOG_ONLY](../../project_paths.py)`.

