"""Health check route for the ARGUS backend."""

from fastapi import APIRouter, status

router = APIRouter(tags=["health"])


@router.get("/health", status_code=status.HTTP_200_OK)
def health_check() -> dict[str, str]:
    """Return a simple liveness response for the API process."""
    return {"status": "ok"}

