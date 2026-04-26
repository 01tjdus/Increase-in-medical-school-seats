# `data/blog_only/` — 블로그 전용

블로그만 따로 받거나, **이 저장소의 블로그 크롤러**로 직접 쌓은 파일을 두는 폴더입니다.

| 파일명 | 의미 | 생성 | 다음 단계 |
|--------|------|------|-----------|
| `naver_blog_medical_quota.csv` | 검색·기간별로 모은 블로그 글 본문·댓글 등 | [`notebooks/00_crolling/naver_crawler.py`](../../notebooks/00_crolling/naver_crawler.py) (기본 출력) | 협업 파이프라인에서 `combined_section_sorted.csv` 등과 합쳐 `data/integrated/`로 |
| `naver_blog_medical_quota_links.csv` | 수집 링크 체크포인트 | `naver_crawler.py` | 크롤 재시작 시 이어 받기 |

`naver_crawler.py`는 `--output`, `--links-output`으로 경로를 바꿀 수 있습니다. 기본값은 **항상 이 폴더**(저장소 루트 기준)입니다.

- 협업자가 블로그 CSV만 넘겨준 경우: 파일명을 정리해 두고 위 표에 한 줄 추가하면 됩니다.
- 카페만 쓰는 경우: 이 폴더는 비워 두고 [`data/cafe_only/`](../cafe_only/README.md)와 [`data/integrated/`](../integrated/README.md)만 사용합니다.

경로 상수: [`project_paths.DATA_BLOG_ONLY`](../../project_paths.py).
