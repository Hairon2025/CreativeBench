"""Small typed boundary between Streamlit and FastAPI."""

from typing import Any

import httpx


class CreativeBenchAPIError(RuntimeError):
    """User-facing API error carrying a concise message."""


class CreativeBenchClient:
    def __init__(self, base_url: str, *, timeout_seconds: float = 120) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
    ) -> Any:
        try:
            response = httpx.request(
                method,
                f"{self.base_url}{path}",
                json=json,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as error:
            try:
                detail = error.response.json().get("detail", error.response.text)
            except ValueError:
                detail = error.response.text
            raise CreativeBenchAPIError(str(detail)) from error
        except httpx.HTTPError as error:
            raise CreativeBenchAPIError(f"无法连接 API：{error}") from error

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def classify(self, prompt_text: str, prompt_id: str | None = None) -> dict[str, Any]:
        payload = {"prompt_text": prompt_text}
        if prompt_id:
            payload["prompt_id"] = prompt_id
        return self._request("POST", "/api/v1/classifications", json=payload)

    def scan(self, prompt_text: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/security/scan",
            json={"prompt_text": prompt_text},
        )

    def reviews(self) -> list[dict[str, Any]]:
        return self._request("GET", "/api/v1/reviews")

    def submit_review(
        self,
        task_id: int,
        *,
        reviewer: str,
        notes: str | None,
        corrected_prediction: dict[str, Any] | None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/v1/reviews/{task_id}",
            json={
                "reviewer": reviewer,
                "notes": notes,
                "corrected_prediction": corrected_prediction,
            },
        )

    def stats(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/stats")
