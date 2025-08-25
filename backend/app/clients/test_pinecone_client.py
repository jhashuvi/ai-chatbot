# app/clients/test_pinecone_client.py
"""
Test script for PineconeClient to verify search functionality and response parsing.
Examines both raw Pinecone API responses and the normalized client output.
"""
import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from pinecone import Pinecone
from app.config import settings
from app.clients.pinecone_client import PineconeClient

def probe_raw_once():
    """
    Probe the raw Pinecone API response structure to understand the data format.
    This helps debug what the actual API returns vs what our client expects.
    """
    from pinecone import Pinecone
    from app.config import settings

    # Initialize direct Pinecone client for raw API testing
    pc = Pinecone(api_key=settings.PINECONE_API_KEY)
    idx = pc.Index(settings.PINECONE_INDEX, host=(settings.PINECONE_HOST or None))

    # Test search query to see raw response structure
    payload = {"inputs": {"text": "verify account"}, "top_k": 3}
    res = idx.search(namespace="__default__", query=payload)

    # Convert response to dict format for inspection
    # Try different methods since Pinecone SDK response format can vary 
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

    # Inspect the top-level structure of the response
    print("keys:", list(d.keys()))
    result = d.get("result")
    if isinstance(result, dict):
        print("result.keys:", list(result.keys()))
        # Look at the hits array which contains individual search results
        hits = result.get("hits", [])
        print("result.hits len:", len(hits))

        if hits:
            # Examine the first hit to understand its structure
            first = hits[0]
            if hasattr(first, "to_dict"):
                first = first.to_dict()
            print("first hit keys:", list(first.keys()))

            # Look at the fields which contain the actual content
            fields = first.get("fields", {})
            if hasattr(fields, "to_dict"):
                fields = fields.to_dict()
            if isinstance(fields, dict):
                print("first hit.fields keys:", list(fields.keys()))
                # Try to extract text content from various possible field names
                txt = fields.get("text") or fields.get("content") or fields.get("page_content") or fields.get("body") or fields.get("raw")
                print("first hit text preview:", (txt or "")[:200])
    print()


def print_preview(chunks):
    """
    Print the normalized search results from our PineconeClient.
    Shows chunk ID, score, source, metadata, and a preview of the text content.
    """
    for i, c in enumerate(chunks, 1):
        # Clean up text for display by removing newlines
        text = (c.get("content") or "").replace("\n", " ")
        score = c.get("score")
        score_s = f"{score:.3f}" if isinstance(score, (int, float)) else "None"
        
        # Clean up metadata for readability by removing redundant text fields
        meta = dict(c.get("metadata", {}))
        for k in ("text", "content", "page_content", "body", "raw"):
            meta.pop(k, None)
        
        # Print formatted chunk information
        print(f"[{i}] id={c.get('chunk_id','')} score={score_s}")
        print("    source  :", c.get("source"))
        print("    metadata:", meta)
        print("    text    :", (text[:180] + "…" if len(text) > 180 else text))
        print()

def main():
    """
    Main test function that demonstrates both raw API inspection and client usage.
    Tests multiple queries to verify search functionality works consistently.
    """
    # Show raw structure once so we know what the SDK returns
    probe_raw_once()
    client = PineconeClient(namespace="__default__")

    # Test multiple different queries to verify search works for various topics
    for q in ["verify account", "transfer limit", "report fraud"]:
        chunks, best = client.search(q, top_k=5)
        print(f"== Query: {q!r} | best_score: {best} ==")
        if not chunks:
            print("(no matches)\n")
            continue
        print_preview(chunks)

if __name__ == "__main__":
    main()
