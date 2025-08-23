# app/clients/test_pinecone_client.py
import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from pinecone import Pinecone
from app.config import settings
from app.clients.pinecone_client import PineconeClient

def probe_raw_once():
    from pinecone import Pinecone
    from app.config import settings

    pc = Pinecone(api_key=settings.PINECONE_API_KEY)
    idx = pc.Index(settings.PINECONE_INDEX, host=(settings.PINECONE_HOST or None))

    payload = {"inputs": {"text": "verify account"}, "top_k": 3}
    res = idx.search(namespace="__default__", query=payload)

    d = None
    for attr in ("to_dict", "model_dump"):
        fn = getattr(res, attr, None)
        if callable(fn):
            try:
                d = fn()
                break
            except Exception:
                pass
    if d is None and isinstance(res, dict):
        d = res

    print("== Raw response (dict view) ==")
    if not isinstance(d, dict):
        print("(could not obtain dict view; type:", type(res), ")")
        print()
        return

    print("keys:", list(d.keys()))
    result = d.get("result")
    if isinstance(result, dict):
        print("result.keys:", list(result.keys()))
        hits = result.get("hits", [])
        print("result.hits len:", len(hits))
        if hits:
            first = hits[0]
            if hasattr(first, "to_dict"):
                first = first.to_dict()
            print("first hit keys:", list(first.keys()))
            fields = first.get("fields", {})
            if hasattr(fields, "to_dict"):
                fields = fields.to_dict()
            if isinstance(fields, dict):
                print("first hit.fields keys:", list(fields.keys()))
                txt = fields.get("text") or fields.get("content") or fields.get("page_content") or fields.get("body") or fields.get("raw")
                print("first hit text preview:", (txt or "")[:200])
    print()


def print_preview(chunks):
    for i, c in enumerate(chunks, 1):
        text = (c.get("content") or "").replace("\n", " ")
        score = c.get("score")
        score_s = f"{score:.3f}" if isinstance(score, (int, float)) else "None"
        # Hide full text in metadata for readability
        meta = dict(c.get("metadata", {}))
        for k in ("text", "content", "page_content", "body", "raw"):
            meta.pop(k, None)
        print(f"[{i}] id={c.get('chunk_id','')} score={score_s}")
        print("    source  :", c.get("source"))
        print("    metadata:", meta)
        print("    text    :", (text[:180] + "…" if len(text) > 180 else text))
        print()

def main():
    # 1) Show raw structure once so we know what the SDK returns
    probe_raw_once()

    # 2) Use your integrated client for actual chunks/scores
    client = PineconeClient(namespace="__default__")

    for q in ["verify account", "transfer limit", "report fraud"]:
        chunks, best = client.search(q, top_k=5)
        print(f"== Query: {q!r} | best_score: {best} ==")
        if not chunks:
            print("(no matches)\n")
            continue
        print_preview(chunks)

if __name__ == "__main__":
    main()
