# Testing — Health Rec System

Tài liệu này hướng dẫn chạy test, tạo fixture mới và debug khi fail.

## 1. Cài dependencies

```bash
pip install -r requirements.txt
```

Trong đó đã bao gồm:
- `pytest==8.3.4` — runner.
- `pytest-flask==1.3.0` — hỗ trợ `client` cho Flask.
- `pytest-mock==3.14.0` — wrapper gọn cho `unittest.mock`.

## 2. Chạy test

```bash
# Toàn bộ
pytest

# Một file
pytest tests/test_departments.py

# Một test cụ thể (theo tên function)
pytest tests/test_auth.py::test_logout_revokes_token -v

# Dừng ở lỗi đầu tiên
pytest -x

# Dùng pdb khi fail
pytest --pdb
```

## 3. Cấu trúc

```
tests/
├── conftest.py        # Fixture dùng chung: app, client, db, auth_header, mock R2/Google
├── test_health.py     # /health
├── test_auth.py       # /api/v1/auth/*  (google url/callback, me, logout)
├── test_departments.py# /api/v1/departments/*  (list, stats, create, update)
├── test_symptoms.py   # /api/v1/symptoms/*  (categories + symptoms)
├── test_doctors.py    # /api/v1/doctors  (phân quyền admin vs dept_head)
├── test_uploads.py    # /api/v1/uploads/*  (presign, confirm)
└── README_TESTING.md  # File này
```

## 4. Quy ước đặt tên

| Loại | Pattern | Ví dụ |
|---|---|---|
| File | `test_<module>.py` | `test_auth.py` |
| Function | `test_<action>_<expected>` | `test_create_department_returns_201` |
| Fixture (conftest) | danh từ / role | `admin_user`, `auth_header`, `make_token` |

## 5. Các fixture chính

| Fixture | Trả về | Dùng cho |
|---|---|---|
| `app` | Flask app, DB `:memory:` đã drop + create | bất kỳ |
| `client` | `app.test_client()` | gọi HTTP |
| `db` | SQLAlchemy session | query, create trực tiếp |
| `admin_user` | user có permission `department:manage`, `symptom:manage` | test quản trị |
| `dept_head_user` | user chỉ có `department:manage`, không phải admin | test phân quyền |
| `plain_user` | user không có permission gì | test 403 |
| `auth_header(user)` | dict `{"Authorization": "Bearer ..."}` | gắn vào `client.get/post` |
| `make_token(user)` | `(token, expires_at)` | test token thủ công |
| `mock_external_services` | dict các MagicMock cho `exchange_google_code`, `presign_put/get`, `head_exists` | test không phụ thuộc R2/Google thật |

## 6. Pattern thường dùng

### Test endpoint cần auth

```python
def test_xxx(client, auth_header, plain_user):
    headers = auth_header(plain_user)
    response = client.get("/api/v1/xxx", headers=headers)
    assert response.status_code == 200
```

### Test endpoint yêu cầu permission

```python
def test_xxx_requires_permission(client, auth_header, plain_user):
    # plain_user KHÔNG có permission nên phải trả 403.
    response = client.post(
        "/api/v1/xxx",
        headers=auth_header(plain_user),
        json={"name": "test"},
    )
    assert response.status_code == 403
```

### Test mock service ngoài

```python
def test_upload(monkeypatch, client, auth_header, plain_user):
    from app.services import storage as _storage_mod
    monkeypatch.setattr(_storage_mod, "head_exists", lambda key: True)

    response = client.post(...)
```

## 7. Lỗi thường gặp

| Lỗi | Nguyên nhân & sửa |
|---|---|
| `RuntimeError: Working outside of application context` | gọi model ngoài `app.app_context()` → đảm bảo dùng `db.session.add(...)` qua fixture `db` (fixture này đã có app context) |
| `AssertionError: 422 != 400` | nhầm lẫn giữa validation (422) và business rule (400) |
| `AssertionError: 401 != 200` | token hết hạn / chưa gắn header / bị blacklist |
| Test chạy OK từng file nhưng fail khi chạy all | do fixture `app` chưa set `scope="function"` — nên mỗi test có app riêng |
| `sqlite3.OperationalError: no such table` | bỏ qua `db.drop_all()` / `db.create_all()` trong fixture `app` — kiểm tra `conftest.py` |

## 8. Khi test fail ở CI (Sonar / GitHub Actions)

```yaml
- name: Run tests
  run: |
    python -m pytest --junitxml=test-report.xml
- name: Publish results
  uses: actions/upload-artifact@v4
  with:
    name: test-report
    path: test-report.xml
```

Job fail → tải artifact `test-report.xml` để xem chi tiết.
