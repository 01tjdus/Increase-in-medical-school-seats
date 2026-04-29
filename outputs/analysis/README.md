# `outputs/analysis/` — 분석 산출물

이 폴더는 `notebooks/02_integrated/integrated_preprocessing.ipynb`의 불용어 후보 CSV와 `notebooks/03_analysis/section_analysis.ipynb`의 최종 분석 결과가 저장되는 위치입니다. 루트에는 설명 파일만 두고, 실제 CSV·PNG·HTML 결과는 하위 폴더에 분리해 둡니다.

| 폴더 | 산출물 의미 |
| --- | --- |
| `tfidf/` | 02 단계 고착어·고유어 후보 CSV, 03 단계 구간별 TF-IDF 상위어와 히트맵 |
| `wordcloud/` | 최종 토큰 기준 구간별 워드클라우드 요약 이미지 |
| `kmeans/` | 엘보 분석, 군집별 키워드, 문서별 군집, 구간별 군집 비율, 박스플롯 |
| `lda/` | LDA/NMF 토픽별 키워드, 문서별 대표 토픽, 구간별 토픽 비율 |
| `stopwords/` | 불용어 후보 또는 사전 점검 결과 |
| `datasets/` | 필요 시 생성되는 대용량 중간 테이블 |
