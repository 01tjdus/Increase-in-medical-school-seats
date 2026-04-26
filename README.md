# 의대 증원 온라인 여론 분석

네이버 블로그·카페의 `의대 증원` 관련 게시글을 수집해, 2024년 1월부터 2025년 6월까지의 담론 변화를 4개 구간(section)으로 나누어 분석한 프로젝트입니다.

## 문서 안내
- 프로젝트 구조와 실행 순서: [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)
- 분석 설계와 방법론: [ANALYSIS_PLAN.md](ANALYSIS_PLAN.md)
- 발표 구성안: [PPT_OUTLINE.md](PPT_OUTLINE.md)

## 실행 개요
1. 선택 실행: 카페·블로그 크롤링 (`notebooks/00_crolling/`)
2. 카페·블로그 전처리 및 통합 (`notebooks/01_preprocess/`, `notebooks/02_integrated/`)
3. 메인 분석 실행 (`notebooks/03_analysis/section_analysis_pipeline.ipynb`)

필요 패키지는 다음 명령으로 설치합니다.

```bash
pip install -r requirements_pipeline.txt
```
