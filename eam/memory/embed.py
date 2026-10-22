"""Embedders for memory retrieval.

``HashingEmbedder`` is an offline bag-of-words fallback (fine for tests, weak on
paraphrase). ``BedrockTitanEmbedder`` calls Amazon Titan Text Embeddings V2.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Protocol

STOPWORDS = set("a an the and or of to in on for with at by is are was were be been it this that what which who "
                "do does did i you my your me we our they them he she his her its as from so if but not no".split())


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


def _terms(text: str) -> list[str]:
    out = []
    for w in re.findall(r"[a-z0-9]+", text.lower()):
        if w in STOPWORDS:
            continue
        for suffix in ("ing", "ed", "es", "s"):
            if len(w) > 4 and w.endswith(suffix):
                w = w[: -len(suffix)]
                break
        out.append(w)
    return out


class HashingEmbedder:
    def __init__(self, dim: int = 512):
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        vecs = []
        for text in texts:
            v = [0.0] * self.dim
            for term in _terms(text):
                v[int(hashlib.md5(term.encode()).hexdigest(), 16) % self.dim] += 1.0
            norm = math.sqrt(sum(x * x for x in v)) or 1.0
            vecs.append([x / norm for x in v])
        return vecs


class BedrockTitanEmbedder:
    def __init__(self, model_id: str = "amazon.titan-embed-text-v2:0", dimensions: int = 512, client=None,
                 region: str | None = None):
        if client is None:
            import boto3

            client = boto3.client("bedrock-runtime", region_name=region)
        self._client = client
        self.model_id = model_id
        self.dimensions = dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for text in texts:
            resp = self._client.invoke_model(
                modelId=self.model_id,
                body=json.dumps({"inputText": text, "dimensions": self.dimensions, "normalize": True}),
            )
            out.append(json.loads(resp["body"].read())["embedding"])
        return out


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))
