from dataclasses import dataclass
from typing import Any, Mapping

import httpx


class APIError(RuntimeError):
    """Özelleştirilmiş API hata türü."""

    def __init__(self, message: str, *, status_code: int | None = None, response: httpx.Response | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response = response

    def __str__(self) -> str:
        prefix = f"[{self.status_code}] " if self.status_code is not None else ""
        return f"{prefix}{super().__str__()}"


def _extract_error_message(response: httpx.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return response.text or "Bilinmeyen sunucu hatası"

    if isinstance(data, Mapping):
        detail = data.get("detail")
        if isinstance(detail, str):
            return detail
        if isinstance(detail, Mapping) and "msg" in detail:
            return str(detail["msg"])
    return "İşlem sırasında bir hata oluştu"


@dataclass(slots=True)
class AuraAPIClient:
    """FastAPI servis entegrasyonu için küçük istemci."""

    base_url: str
    token: str | None = None
    timeout: float = 10.0

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = self._build_url(path)
        headers: dict[str, str] = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        headers.update(kwargs.pop("headers", {}))

        try:
            response = httpx.request(method, url, headers=headers, timeout=self.timeout, **kwargs)
        except httpx.HTTPError as exc:  # pragma: no cover - ağ hataları manuel test edilir
            raise APIError(f"API isteği başarısız oldu: {exc}") from exc

        if response.status_code >= 400:
            message = _extract_error_message(response)
            raise APIError(message, status_code=response.status_code, response=response)

        if response.status_code == 204:
            return None

        if not response.content:
            return None

        content_type = response.headers.get("Content-Type", "")
        if "application/json" in content_type:
            return response.json()
        return response.text

    def _build_url(self, path: str) -> str:
        normalized = path if path.startswith("/") else f"/{path}"
        return f"{self.base_url.rstrip('/')}{normalized}"

    # Sağlık kontrolleri
    def ping(self) -> Mapping[str, Any]:
        return self._request("GET", "/ping")

    def secure_ping(self) -> Mapping[str, Any]:
        return self._request("GET", "/ping/secure")

    # Yanıt derleyici
    def compile_answer(self, *, answer: str, documents: list[Mapping[str, Any]] | None = None) -> Mapping[str, Any]:
        payload = {"answer": answer, "documents": documents or []}
        return self._request("POST", "/answers", json=payload)

    # Ticket servisi işlemleri
    def list_tickets(self) -> list[Mapping[str, Any]]:
        data = self._request("GET", "/tickets")
        return list(data or [])

    def create_ticket(
        self,
        *,
        title: str,
        content: str,
        priority: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        payload = {
            "title": title,
            "content": content,
            "priority": priority,
            "metadata": metadata or {},
        }
        return self._request("POST", "/tickets", json=payload)

    def get_ticket(self, ticket_id: str) -> Mapping[str, Any]:
        return self._request("GET", f"/tickets/{ticket_id}")

    def add_ticket_message(self, ticket_id: str, *, content: str) -> Mapping[str, Any]:
        payload = {"content": content}
        return self._request("POST", f"/tickets/{ticket_id}/messages", json=payload)

    def change_ticket_status(
        self,
        ticket_id: str,
        *,
        status: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        payload = {"status": status, "metadata": metadata or {}}
        return self._request("POST", f"/tickets/{ticket_id}/status", json=payload)

    def delete_ticket(self, ticket_id: str) -> None:
        self._request("DELETE", f"/tickets/{ticket_id}")
