"""Schlage service layer wrapping the pyschlage library.

All direct interactions with the pyschlage library are encapsulated in
this module. FastAPI endpoints should call methods here and avoid
importing or using pyschlage directly.

The service loads credentials from environment variables via python-dotenv:
- SCHLAGE_USERNAME
- SCHLAGE_PASSWORD

Raises:
    SchlageServiceError: For any recoverable, user-facing error conditions.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, asdict, is_dataclass
import traceback
import sys
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv


class SchlageServiceError(Exception):
    """Domain error for Schlage service operations."""


@dataclass
class LockSummary:
    """A minimal summary of a lock."""

    device_id: str
    name: Optional[str]


class SchlageService:
    """Encapsulates all interactions with the pyschlage library.

    This class defers imports until initialization to keep the module importable
    even if the dependency is not yet installed.
    """

    def __init__(self) -> None:
        """Initialize the Schlage client using environment credentials.

        Environment variables expected:
            SCHLAGE_USERNAME: Schlage account email/username
            SCHLAGE_PASSWORD: Schlage account password

        Raises:
            SchlageServiceError: If credentials are missing or client init fails.
        """

        load_dotenv()

        username = os.getenv("SCHLAGE_USERNAME")
        password = os.getenv("SCHLAGE_PASSWORD")
        if not username or not password:
            raise SchlageServiceError(
                "SCHLAGE_USERNAME and SCHLAGE_PASSWORD must be set in the .env file"
            )

        try:
            # Import here to avoid hard dependency at module import time
            from pyschlage import Auth, Schlage  # type: ignore

            auth = Auth(username, password)
            self._schlage = Schlage(auth)
        except Exception as exc:  # pragma: no cover - best-effort safety
            raise SchlageServiceError(f"Failed to initialize Schlage client: {exc}") from exc

    # ---------- Internal helpers ----------
    def _fetch_locks(self) -> List[Any]:
        """Return underlying lock objects from pyschlage.

        Tries common method names to remain resilient to minor API changes.
        """

        # Prefer a callable method
        for attr in ("locks", "get_locks"):
            obj = getattr(self._schlage, attr, None)
            if callable(obj):
                return list(obj())

        # If presented as a property/attribute
        for attr in ("locks", "devices"):
            obj = getattr(self._schlage, attr, None)
            if obj is not None:
                try:
                    return list(obj)
                except TypeError:
                    pass

        raise SchlageServiceError("Unable to retrieve locks from pyschlage client")

    def _find_lock(self, device_id: str) -> Any:
        """Find and return the raw lock object by device_id.

        Args:
            device_id: The unique identifier for the Schlage lock.

        Raises:
            SchlageServiceError: If no matching lock is found.
        """

        locks = self._fetch_locks()
        for lock in locks:
            if getattr(lock, "device_id", None) == device_id or getattr(lock, "id", None) == device_id:
                return lock
        raise SchlageServiceError("Lock not found")

    @staticmethod
    def _maybe_call(obj: Any, *args: Any, **kwargs: Any) -> Any:
        """Call obj if callable, otherwise return as-is."""

        return obj(*args, **kwargs) if callable(obj) else obj

    # ---------- Public API ----------
    def list_locks(self) -> List[LockSummary]:
        """List available locks with minimal identifying info.

        Returns:
            A list of LockSummary for each discovered lock.
        """

        results: List[LockSummary] = []
        for lock in self._fetch_locks():
            results.append(
                LockSummary(
                    device_id=getattr(lock, "device_id", getattr(lock, "id", "")),
                    name=getattr(lock, "name", None),
                )
            )
        return results

    def get_lock_details(self, device_id: str) -> Dict[str, Any]:
        """Gets detailed information for a specific lock.

        Args:
            device_id: The unique identifier for the Schlage lock.

        Returns:
            A dictionary containing the lock's details.
        """

        lock = self._find_lock(device_id)

        # Attempt a refresh if supported
        refresh = getattr(lock, "refresh", None)
        if callable(refresh):
            try:
                refresh()
            except Exception:
                # Non-fatal; return whatever state is available
                pass

        return {
            "device_id": getattr(lock, "device_id", getattr(lock, "id", device_id)),
            "name": getattr(lock, "name", None),
            "is_locked": getattr(lock, "is_locked", None),
            "is_jammed": getattr(lock, "is_jammed", None),
            "battery_level": getattr(lock, "battery_level", None),
            "firmware_version": getattr(lock, "firmware_version", None),
        }

    def lock_device(self, device_id: str) -> Dict[str, Any]:
        """Lock the specified device.

        Returns:
            A status payload indicating the result.
        """

        lock = self._find_lock(device_id)
        action = getattr(lock, "lock", None)
        if not callable(action):
            raise SchlageServiceError("Lock action not supported by this device")

        action()
        return {"device_id": device_id, "action": "lock", "status": "requested"}

    def unlock_device(self, device_id: str) -> Dict[str, Any]:
        """Unlock the specified device.

        Returns:
            A status payload indicating the result.
        """

        lock = self._find_lock(device_id)
        action = getattr(lock, "unlock", None)
        if not callable(action):
            raise SchlageServiceError("Unlock action not supported by this device")

        action()
        return {"device_id": device_id, "action": "unlock", "status": "requested"}

    def get_logs(self, device_id: str) -> List[Dict[str, Any]]:
        """Retrieve recent logs/events for a device, if supported.

        Returns:
            A list of event dictionaries, if available.
        """

        lock = self._find_lock(device_id)
        # Try a range of likely attributes or methods
        for attr in ("get_logs", "logs", "history", "events", "activities"):
            candidate = getattr(lock, attr, None)
            if candidate is None:
                continue
            try:
                data = self._maybe_call(candidate)
                if data is None:
                    return []

                # Normalize to a list of items
                if isinstance(data, list):
                    items = data
                elif isinstance(data, dict):
                    items = list(data.values())
                else:
                    try:
                        items = list(data)
                    except Exception:
                        items = [data]

                # Convert each item to a serializable dict, handling dataclasses
                result: List[Dict[str, Any]] = []
                for item in items:
                    if isinstance(item, dict):
                        result.append(item)
                    elif is_dataclass(item):
                        result.append(asdict(item))
                    else:
                        # Fallbacks: try dict(item), then vars(), then str()
                        try:
                            result.append(dict(item))
                        except Exception:
                            try:
                                result.append(vars(item))
                            except Exception:
                                result.append({"value": str(item)})
                return result
            except Exception:
                # Try next candidate
                continue

        # Not supported
        raise SchlageServiceError("Logs are not available for this device")

    def get_access_codes(self, device_id: str) -> List[Dict[str, Any]]:
        """Retrieve access/pin codes for a device, if supported.

        Returns:
            A list of access code entries.
        """
        lock = self._find_lock(device_id)
        try:
            # Step 1: Attempt to refresh the codes first
            refresh_method = getattr(lock, "refresh_access_codes", None)
            if callable(refresh_method):
                refresh_method()

            # Step 2: Attempt to access the codes attribute
            codes_attr = getattr(lock, "access_codes", None)
            if codes_attr is None:
                raise SchlageServiceError("Access codes attribute not found on lock object.")

            if isinstance(codes_attr, dict):
                data_source = codes_attr.values()
            elif isinstance(codes_attr, list):
                data_source = codes_attr
            else:
                try:
                    data_source = list(codes_attr)
                except TypeError:
                    data_source = [codes_attr]

            def _serialize_datetime(value: Any) -> Any:
                if value is None:
                    return None
                iso = getattr(value, "isoformat", None)
                if callable(iso):
                    return iso()
                return str(value)

            results: List[Dict[str, Any]] = []
            for item in data_source:
                schedule_obj = getattr(item, "schedule", None)
                schedule_payload: Optional[Dict[str, Any]]
                if schedule_obj is None:
                    schedule_payload = None
                else:
                    schedule_payload = {
                        "start": _serialize_datetime(getattr(schedule_obj, "start", None)),
                        "end": _serialize_datetime(getattr(schedule_obj, "end", None)),
                    }

                results.append(
                    {
                        "name": getattr(item, "name", None),
                        "code": getattr(item, "code", None),
                        "disabled": getattr(item, "disabled", None),
                        "notify_on_use": getattr(item, "notify_on_use", None),
                        "schedule": schedule_payload,
                    }
                )

            return results

        except Exception:
            print("--- AN EXCEPTION OCCURRED IN GET_ACCESS_CODES ---", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            print("-------------------------------------------------", file=sys.stderr)
            raise SchlageServiceError(
                "Access codes are not available for this device due to an internal error."
            )
