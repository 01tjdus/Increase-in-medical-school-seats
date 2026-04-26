# `outputs/pipeline/` — 분석 산출물

이 폴더는 `notebooks/03_analysis/section_analysis_pipeline.ipynb` 실행 결과가 저장되는 위치입니다. 루트에는 설명 파일만 두고, 실제 CSV·PNG·HTML 결과는 하위 폴더에 분리해 둡니다.

| 폴더 | 산출물 의미 |
| --- | --- |
| `tfidf/` | 구간별 TF-IDF 상위어, 고유어 후보, 고착어 후보, TF-IDF 히트맵 |
| `wordcloud/` | 구간별 워드클라우드 요약 이미지 |
| `wordcloud/raw/` | 불용어 적용 전 구간별 워드클라우드·상위 단어표 |
| `wordcloud/filtered/` | 불용어 적용 후 구간별 워드클라우드·상위 단어표 |
| `kmeans/` | 엘보 분석, 군집별 키워드, 문서별 군집, 구간별 군집 비율, 박스플롯 |
| `lda/` | 토픽별 키워드, 문서별 대표 토픽, 구간별 토픽 비율, 토픽 히트맵 |
| `sentiment/` | 사전 기반 경량 감성 점수의 구간별 요약 |
| `stopwords/` | 불용어 후보 또는 사전 점검 결과 |
| `datasets/` | 필요 시 생성되는 대용량 중간 테이블 |
