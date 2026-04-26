# Pipeline Outputs

- **루트(`outputs/pipeline/`)**: 가능하면 비워 두고, CSV·PNG는 하위 폴더에 둡니다.
- **`tfidf/`**: `03_analysis/section_analysis_pipeline.ipynb`가 쓰는 TF-IDF wide CSV, 고착어·고유어 후보 CSV, 히트맵 PNG 등.
- **`wordcloud/`**: 구간별 워드클라우드 PNG(`wordcloud_by_section.png`, `wordcloud_bf_stopwords.png`, `tfidf_heatmap_union_top.png` 등).
- `datasets/`: large intermediate tables kept local, such as token-expanded analysis tables.
- `kmeans/`: elbow results, cluster keywords, and document-to-cluster assignments.
- `lda/`: topic keywords and dominant-topic tables.
- `stopwords/`: automatically generated stopword candidate tables.
- `tfidf/`: TF-IDF summary tables.
- `wordcloud/raw/`: pre-stopword wordcloud images and top-token tables.
- `wordcloud/filtered/`: post-stopword wordcloud images and top-token tables.
