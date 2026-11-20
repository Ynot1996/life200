"""Rank jobs by how well they fit a life profile.

TF-IDF turns each text into a vector of word weights (rare, specific words count more than
common ones); cosine similarity then measures how much a job and the profile overlap.
Simple, fast, explainable: the top shared words are shown as the reason.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore[import-untyped]
from sklearn.metrics.pairwise import cosine_similarity  # type: ignore[import-untyped]


@dataclass(frozen=True, slots=True)
class Ranked:
    scores: np.ndarray  # 0-1, one per job
    reasons: list[str]  # top shared words, one per job


def rank_jobs(profile_text: str, jobs: pd.DataFrame, top_words: int = 5) -> Ranked:
    """`jobs` needs Title and Description columns. Returns scores in the same row order."""
    if jobs.empty or not profile_text.strip():
        return Ranked(np.zeros(len(jobs)), [""] * len(jobs))
    docs = (
        jobs["Title"].fillna("")
        + " "
        + jobs["Title"].fillna("")
        + " "
        + jobs["Description"].fillna("")
    ).tolist()
    vectorizer = TfidfVectorizer(
        stop_words="english", ngram_range=(1, 2), sublinear_tf=True, min_df=1
    )
    matrix = vectorizer.fit_transform([profile_text, *docs])
    me, job_vectors = matrix[0], matrix[1:]
    scores = cosine_similarity(me, job_vectors).ravel()

    vocab = np.array(vectorizer.get_feature_names_out())
    shared = job_vectors.multiply(me)  # weight of each word present in both
    reasons = []
    for i in range(shared.shape[0]):
        row = shared.getrow(i).toarray().ravel()
        best = row.argsort()[::-1][:top_words]
        reasons.append(", ".join(vocab[j] for j in best if row[j] > 0))
    return Ranked(scores, reasons)
