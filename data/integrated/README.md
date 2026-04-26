# `data/integrated/` — 블로그 반영 **후** 통합 분석용 데이터

카페 전처리 결과와 협업자 블로그 데이터를 합친 뒤, 구간(`section`)·채널(`ch`) 등이 맞춰진 **통합 코퍼스**가 여기 저장됩니다.

| 파일명 | 의미 | 생성 | 다음 단계에서 읽는 쪽 |
|--------|------|------|------------------------|
| `combined_section_sorted.csv` | 구간·채널 정리된 통합 CSV(원본에 가까운 형태) | 협업 측 제공 + [`notebooks/02_integrated/integrated_pipeline.ipynb`](../../notebooks/02_integrated/integrated_pipeline.ipynb)에서 보정 | `integrated_pipeline.ipynb` |
| `crolling_total_estate_press.pkl` | 토큰·명사 컬럼 정리된 **메인 분석용 PKL** (블로그+카페) | `integrated_pipeline.ipynb` | [`notebooks/03_analysis/section_analysis_pipeline.ipynb`](../../notebooks/03_analysis/section_analysis_pipeline.ipynb) |
| `crolling_total_estate_press_layered.pkl` | 공통·섹션 로컬 불용어 적용 후 `*_raw`→`*_clean`→`*_final`·`nouns_final` 레이어가 붙은 최종 PKL | `section_analysis_pipeline.ipynb` | 보고·추가 모델링·재현 시 |
| `combined_section_sorted_flat_comments.pkl` | (있을 경우) 댓글 평탄화 등 **실험/레거시** 입력용 | [`notebooks/01_preprocess/blog_flat_preprocess.ipynb`](../../notebooks/01_preprocess/blog_flat_preprocess.ipynb) 또는 과거 파이프라인 | [`notebooks/03_analysis/section_analysis_pipeline.ipynb`](../../notebooks/03_analysis/section_analysis_pipeline.ipynb)의 flat 섹션 — **메인 PKL과 스키마가 다를 수 있음** |

경로 상수: [`project_paths.DATA_INTEGRATED`](../../project_paths.py).
