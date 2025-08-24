"""
Health check endpoint for service monitoring and readiness probes.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/healthz", tags=["health"])

@router.get("")
def health_check():
    return {"status": "ok"}
