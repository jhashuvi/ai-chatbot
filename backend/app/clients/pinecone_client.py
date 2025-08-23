# app/clients/pinecone_client.py
from __future__ import annotations
from typing import Any, Dict, List, Tuple, Optional, Union
from pinecone import Pinecone
from app.config import settings

def _to_matches(res: Any) -> List[Dict[str, Any]]:
    """
    Normalize Pinecone search responses to a list of {id, score, metadata, text, source} dicts.
    Supports:
      - d["matches"]
      - d["data"]["matches"]
      - d["results"][0]["matches"]
      - d["result"]["matches"]
      - d["result"]["hits"]  <-- new “search records” shape (your SDK)
    """
    # 1) Produce a plain dict view of the OpenAPI model
    d: Dict[str, Any]
    if isinstance(res, dict):
        d = res
    else:
        for attr in ("to_dict", "model_dump"):
            fn = getattr(res, attr, None)
            if callable(fn):
                try:
                    d = fn()
                    break
                except Exception:
                    pass
        else:
            return []

    def get_in(obj: Any, path: List[Union[str, int]], default=None):
        cur = obj
        for p in path:
            if isinstance(p, int):
                if isinstance(cur, list) and 0 <= p < len(cur):
                    cur = cur[p]
                else:
                    return default
            else:
                if isinstance(cur, dict) and p in cur:
                    cur = cur[p]
                else:
                    return default
        return cur

    # 2) Legacy / older shapes with "matches"
    for cand in (
        get_in(d, ["matches"]),
        get_in(d, ["data", "matches"]),
        get_in(d, ["results", 0, "matches"]),
        get_in(d, ["result", "matches"]),
        get_in(d, ["result", "data", "matches"]),
    ):
        if isinstance(cand, list) and cand:
            # already in match-ish shape; return as-is (id/score/metadata keys expected)
            return cand

    # 3) New shape: result.hits (list of hits with _id, _score, fields)
    hits = get_in(d, ["result", "hits"])
    if isinstance(hits, list) and hits:
        out: List[Dict[str, Any]] = []
        for h in hits:
            # Ensure dict
            if not isinstance(h, dict):
                # try to_dict on hit object
                for attr in ("to_dict", "model_dump"):
                    fn = getattr(h, attr, None)
                    if callable(fn):
                        try:
                            h = fn()
                            break
                        except Exception:
                            pass
                if not isinstance(h, dict):
                    continue

            hit_id = h.get("_id") or h.get("id")
            score = h.get("_score") or h.get("score")
            fields = h.get("fields") or {}
            if not isinstance(fields, dict):
                # try to_dict on fields
                for attr in ("to_dict", "model_dump"):
                    fn = getattr(fields, attr, None)
                    if callable(fn):
                        try:
                            fields = fn()
                            break
                        except Exception:
                            pass
                if not isinstance(fields, dict):
                    fields = {}

            # Pull text/content and metadata from fields
            text = (
                fields.get("text")
                or fields.get("content")
                or fields.get("page_content")
                or fields.get("body")
                or fields.get("raw")
                or ""
            )
            md = fields.get("metadata")
            if not isinstance(md, dict):
                md = {}

            # Add common useful fields into metadata if present
            for k in ("source", "title", "filename", "category"):
                if k in fields and k not in md:
                    md[k] = fields[k]

            out.append({"id": hit_id, "score": score, "metadata": md, "_text": text})
        return out

    # 4) Nothing recognized
    return []


class PineconeClient:
    """
    Client for an integrated-inference Pinecone index (model: llama-text-embed-v2).
    Sends raw text; Pinecone embeds and returns nearest neighbors.
    """
    def __init__(self, namespace: str = "__default__"):
        self.pc = Pinecone(api_key=settings.PINECONE_API_KEY)
        self.idx = self.pc.Index(settings.PINECONE_INDEX, host=(settings.PINECONE_HOST or None))
        # API 2025-04 requires explicit "__default__" for the default records namespace
        self.namespace = namespace or "__default__"

    def search(self, text: str, top_k: int = 5) -> Tuple[List[Dict[str, Any]], Optional[float]]:
        payload = {"inputs": {"text": text}, "top_k": top_k}
        res = self.idx.search(namespace=self.namespace, query=payload)
        raw = _to_matches(res)

        # If nothing recognized, helpful debug
        if not raw:
            print("[debug] Pinecone returned no recognized matches; type:", type(res))

        chunks: List[Dict[str, Any]] = []
        best = 0.0

        for m in raw:
            # Two sources: legacy "matches" (id/score/metadata) or new hits normalized above
            if not isinstance(m, dict):
                m = {
                    "id": getattr(m, "id", None),
                    "score": getattr(m, "score", None),
                    "metadata": getattr(m, "metadata", None),
                }

            md = m.get("metadata") or {}
            # Prefer the pre-extracted text (from hits) if present
            content = (
                m.get("_text")
                or md.get("text")
                or md.get("content")
                or md.get("page_content")
                or md.get("body")
                or md.get("raw")
                or ""
            )
            source = md.get("source") or md.get("filename") or md.get("title") or "unknown"

            score = m.get("score")
            try:
                score_f = float(score) if score is not None else None
            except Exception:
                score_f = None
            if score_f is not None and score_f > best:
                best = score_f

            chunks.append({
                "chunk_id": m.get("id") or md.get("id") or "",
                "content": content,
                "source": source,
                "metadata": md,
                "score": score_f,
            })

        return chunks, (best if best > 0 else None)
