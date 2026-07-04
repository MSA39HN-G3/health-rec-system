"""Smoke test — đảm bảo app tạo được & health check hoạt động.

Tập trung test business logic ở app/services/ — file này chỉ cần
đảm bảo ứng dụng khởi động được để pytest không vỡ lúc import.
"""
from __future__ import annotations


def test_app_creates(client):
    """GET /health phải trả 200."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}
