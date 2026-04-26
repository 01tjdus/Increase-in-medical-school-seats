# Pipeline Outputs

- **루트(`outputs/pipeline/`)**: `section_tfidf_stopwords_pipeline.ipynb`가 쓰는 TF-IDF wide CSV, 고착어·고유어 후보 CSV, 워드클라우드·히트맵 PNG 등(파일명은 노트북 주석·[PROJECT_STRUCTURE.md](../../PROJECT_STRUCTURE.md) 참고).
- `datasets/`: large intermediate tables kept local, such as token-expanded analysis tables.
- `kmeans/`: elbow results, cluster keywords, and document-to-cluster assignments.
- `lda/`: topic keywords and dominant-topic tables.
- `stopwords/`: automatically generated stopword candidate tables.
- `tfidf/`: TF-IDF summary tables.
- `wordcloud/raw/`: pre-stopword wordcloud images and top-token tables.
- `wordcloud/filtered/`: post-stopword wordcloud images and top-token tables.
