"""FastAPI app exposing Schlage lock functionality via pyschlage.

Endpoints delegate to the SchlageService in app.schlage_service to keep
all pyschlage interactions within the service layer.
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException

from .schlage_service import (
    SchlageService,
    SchlageServiceError,
)


app = FastAPI(title="pyschlage-api", version="0.1.0")


# Instantiate service at startup. If credentials are not present, this will raise
# and the app won't start; add credentials to .env before running.
try:
    schlage_service = SchlageService()
except SchlageServiceError as exc:
    # Delay raising until endpoints are called to allow docs to render.
    schlage_service = None  # type: ignore[assignment]
    _startup_error = exc
else:
    _startup_error = None


def _ensure_service() -> SchlageService:
    """Return a live service instance or raise HTTP 500 with context."""

    global schlage_service
    if schlage_service is not None:
        return schlage_service
    assert _startup_error is not None  # for type checkers
    raise HTTPException(status_code=500, detail=str(_startup_error))


@app.get("/health")
def health() -> Dict[str, str]:
    """Health check endpoint."""

    return {"status": "ok"}


@app.get("/locks")
def list_locks() -> List[Dict[str, Any]]:
    """Returns a list of all Schlage locks."""

    service = _ensure_service()
    try:
        locks = service.list_locks()
    except SchlageServiceError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return [{"device_id": item.device_id, "name": item.name} for item in locks]


@app.get("/locks/{device_id}")
def get_lock_details(device_id: str) -> Dict[str, Any]:
    """Gets detailed information for a specific lock.

    Args:
        device_id: The unique identifier for the Schlage lock.

    Returns:
        A dictionary containing the lock's details.

    Raises:
        HTTPException: If the lock with the specified device_id is not found.
    """

    service = _ensure_service()
    try:
        return service.get_lock_details(device_id)
    except SchlageServiceError as exc:
        # Distinguish not-found vs generic error by message
        status = 404 if "not found" in str(exc).lower() else 500
        raise HTTPException(status_code=status, detail=str(exc))


@app.post("/locks/{device_id}/lock")
def lock_device(device_id: str) -> Dict[str, Any]:
    """Lock the specified device."""

    service = _ensure_service()
    try:
        return service.lock_device(device_id)
    except SchlageServiceError as exc:
        status = 404 if "not found" in str(exc).lower() else 400
        raise HTTPException(status_code=status, detail=str(exc))


@app.post("/locks/{device_id}/unlock")
def unlock_device(device_id: str) -> Dict[str, Any]:
    """Unlock the specified device."""

    service = _ensure_service()
    try:
        return service.unlock_device(device_id)
    except SchlageServiceError as exc:
        status = 404 if "not found" in str(exc).lower() else 400
        raise HTTPException(status_code=status, detail=str(exc))


@app.get("/locks/{device_id}/logs")
def get_logs(device_id: str) -> List[Dict[str, Any]]:
    """Get recent activity logs for a lock."""

    service = _ensure_service()
    try:
        return service.get_logs(device_id)
    except SchlageServiceError as exc:
        status = 404 if "not found" in str(exc).lower() else 501
        raise HTTPException(status_code=status, detail=str(exc))


@app.get("/locks/{device_id}/access_codes")
def get_access_codes(device_id: str) -> List[Dict[str, Any]]:
    """Get access codes (PINs) for a lock."""

    service = _ensure_service()
    try:
        return service.get_access_codes(device_id)
    except SchlageServiceError as exc:
        status = 404 if "not found" in str(exc).lower() else 501
        raise HTTPException(status_code=status, detail=str(exc))
