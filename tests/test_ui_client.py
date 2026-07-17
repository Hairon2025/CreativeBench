import httpx
import pytest

from creativebench.ui.client import CreativeBenchAPIError, CreativeBenchClient


def test_client_raises_readable_api_error(monkeypatch) -> None:
    request = httpx.Request("POST", "http://api/api/v1/classifications")
    response = httpx.Response(
        503,
        request=request,
        json={"detail": "未配置 GLM API Key"},
    )

    def fake_request(*_args, **_kwargs):
        return response

    monkeypatch.setattr(httpx, "request", fake_request)

    with pytest.raises(CreativeBenchAPIError, match="未配置 GLM API Key"):
        CreativeBenchClient("http://api").classify("测试")
