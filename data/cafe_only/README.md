# `data/cafe_only/` — 블로그·통합 **이전** 네이버 카페 전용 데이터

협업으로 블로그 글을 합치기 **전** 단계에서만 쓰는 폴더입니다. 크롤·전처리·형태소까지 카페 데이터만 다룹니다.

| 파일명 | 의미 | 생성 | 다음 단계에서 읽는 쪽 |
|--------|------|------|------------------------|
| `의대증원_카페_v2.json` | 카페 크롤 원본(게시글·댓글 등 누적 JSON) | [`code/의대증원_카페크롤링_v2.py`](../../code/의대증원_카페크롤링_v2.py) | [`notebooks/01_cafe/cafedata_preprocess.ipynb`](../../notebooks/01_cafe/cafedata_preprocess.ipynb) |
| `의대증원_cafedata_preprocess.csv` | JSON 정리·정규화된 표 형태 전처리 결과 | `cafedata_preprocess.ipynb` | [`notebooks/01_cafe/cafedata_total_estate_press.ipynb`](../../notebooks/01_cafe/cafedata_total_estate_press.ipynb) |
| `의대증원_cafedata_total_estate_press.pkl` | Kiwi 명사 추출·1차 불용어(`stopwords-ko`) 적용 후 카페 단독 PKL | `cafedata_total_estate_press.ipynb` | 통합 단계에서 CSV/PKL로 합치거나, 협업 워크플로에 따라 `data/integrated/`로 이관 |
| `의대증원_cafedata_total_estate_press_drop_list_pos.pkl` | POS 리스트 컬럼 제거 버전(용량·분석 단순화) | `cafedata_total_estate_press.ipynb` | 필요 시 통합·분석 노트북 |

경로 상수: [`project_paths.DATA_CAFE_ONLY`](../../project_paths.py).
