# `data/integrated/` — 통합 분석용 데이터

카페 데이터와 블로그 데이터를 합친 뒤, 구간(`section`)·채널(`ch`) 등이 맞춰진 **통합 코퍼스**가 여기 저장됩니다.


| 파일명                                       | 의미                                                                               | 생성                                                                                                                       | 다음 단계에서 읽는 쪽                                                                                         |
| ----------------------------------------- | -------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------- |
| `combined_section_sorted.csv`             | 구간·채널 정리된 통합 CSV(원본에 가까운 형태)                                                     | `[notebooks/02_integrated/integrated_preprocessing.ipynb](../../notebooks/02_integrated/integrated_preprocessing.ipynb)` | 같은 노트북의 PKL 저장 단계                                                                                    |
| `crolling_total_estate_press.pkl`         | 토큰·명사 컬럼 정리된 통합 기준 PKL(불용어 레이어 전)                                                | `integrated_preprocessing.ipynb`                                                                                         | 같은 노트북의 불용어 레이어 단계                                                                                   |
| `crolling_total_estate_press_layered.pkl` | 공통·섹션 로컬 불용어 적용 후 `*_raw`→`*_clean`→`*_final`·`nouns_final` 레이어가 붙은 최종 분석 입력 PKL | `integrated_preprocessing.ipynb`                                                                                         | `[notebooks/03_analysis/section_analysis.ipynb](../../notebooks/03_analysis/section_analysis.ipynb)` |


현재 기준 실행 파일은 `notebooks/02_integrated/integrated_preprocessing.ipynb`이며, 최종 분석은 `notebooks/03_analysis/section_analysis.ipynb`에서 진행합니다.

경로 상수: `[project_paths.DATA_INTEGRATED](../../project_paths.py)`.