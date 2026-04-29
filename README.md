# 의대 증원 온라인 여론 분석

네이버 블로그·카페의 `의대 증원` 관련 게시글을 수집해, 2024년 1월부터 2025년 6월까지의 담론 변화를 4개 구간(section)으로 나누어 분석한 프로젝트입니다.

이 프로젝트는 의대 정원 확대가 단순한 보건의료 정책을 넘어 의료현장 갈등, 대입 전형, 정치·사회 반응으로 확장되는 과정을 온라인 텍스트로 추적합니다. 블로그의 설명형 글과 카페의 반응형 글을 함께 사용해, 정책 이슈가 시간에 따라 어떤 언어와 담론 구조로 바뀌는지 확인합니다.

## 문서 안내
- 프로젝트 구조와 실행 순서: [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)
- 분석 설계와 방법론: [ANALYSIS_PLAN.md](ANALYSIS_PLAN.md)
- 발표 구성안: [PPT_OUTLINE.md](PPT_OUTLINE.md)

## 실행 개요
1. 선택 실행: 카페·블로그 크롤링 (`notebooks/00_crolling/`)
2. 원천별 전처리: 블로그·카페를 각각 정리하고 Kiwi 명사 추출 (`notebooks/01_preprocess/`)
3. 통합·불용어 레이어 생성: 블로그·카페를 합쳐 `base.pkl`과 `layered.pkl` 생성 (`notebooks/02_integrated/integrated_preprocessing.ipynb`)
4. 메인 분석 실행: 확정된 `layered.pkl` 기준 TF-IDF, WordCloud, K-Means, LDA, NMF, 반응 지표 (`notebooks/03_analysis/section_analysis.ipynb`)

발표 기준 산출물은 통합 데이터 기반 `section_analysis.ipynb` 결과만 사용합니다.

## 기대 효과
- 정책 발표 이후 온라인 여론이 어떤 시점에 의료현장 갈등에서 입시·전형 담론으로 이동하는지 확인할 수 있습니다.
- TF-IDF, 군집화, 토픽 모델링, 반응 지표를 결합해 단일 키워드 빈도보다 입체적인 담론 해석이 가능합니다.
- 같은 구조를 다른 공공정책 이슈의 여론 모니터링에도 재사용할 수 있습니다.

필요 패키지는 다음 명령으로 설치합니다.

```bash
pip install -r requirements.txt
```
