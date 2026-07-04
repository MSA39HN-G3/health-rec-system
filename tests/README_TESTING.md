# Testing — Health Rec System

Test tập trung vào `app/services/` (business logic). Mục tiêu:
**coverage > 80% cho `app/services/`**, các folder khác được SonarCloud ignore.

## Cấu trúc

```
tests/
├── conftest.py                    # Fixture: app, db, make_role/user/permission, mock_external_services
├── test_health.py                 # Smoke test (1 test)
├── test_services_symptom.py       # SymptomService
├── test_services_department.py    # DepartmentService (logic nặng nhất)
├── test_services_auth.py          # AuthService (OAuth + token + blacklist)
├── test_services_doctor.py        # DoctorService (phân quyền admin vs dept_head)
├── test_services_role_user.py     # RoleService + UserService
├── test_services_storage.py       # Cloudflare R2 helpers
├── test_services_google_oauth.py  # google_oauth (state, build URL, exchange, verify)
├── test_services_token.py         # token_service (issue/decode JWT)
└── README_TESTING.md              # File này
```

## Chạy

```bash
pip install -r requirements.txt

# Toàn bộ test
pytest

# Chỉ test 1 service
pytest tests/test_services_department.py

# 1 test class cụ thể
pytest tests/test_services_doctor.py::TestListDoctors

# Xem coverage report trong terminal (không XML)
pytest --cov=app --cov-report=term-missing

# Sinh XML cho SonarCloud
pytest --cov=app --cov-branch --cov-report=xml:reports/coverage.xml \
       --junitxml=reports/pytest-junit.xml
```

## Coverage

| File phạm vi | Quy tắc |
|---|---|
| `app/services/**` | **Được đo** — mục tiêu ≥ 80% |
| `app/api/**` | Không đo (wiring/transport) |
| `app/models/**` | Không đo (ORM, đơn giản) |
| `app/repositories/**` | Không đo (data access) |
| `app/middleware/**` | Không đo |
| `app/common/**, errors/**, i18n/**` | Không đo |

Cấu hình ở `.coveragerc` (dùng `source = app/services` + `omit`).

Khi push lên GitHub → CI đẩy `reports/coverage.xml` lên SonarCloud →
SonarCloud vẽ tab Coverage và so với Quality Gate (>80% trên services).

## Pattern thường dùng

### Test service với mock repository (nhanh nhất)

```python
from unittest.mock import MagicMock
from app.services.department_service import DepartmentService

def test_xxx():
    d_repo = MagicMock()
    d_repo.find_by_id.return_value = MagicMock()
    svc = DepartmentService(department_repository=d_repo)

    result = svc.update_department(1, name="Mới")
    assert result.name == "Mới"
```

### Test với DB in-memory (chậm hơn nhưng test integration thật)

```python
def test_xxx(db, make_role, make_user):
    role = make_role("admin", ["department:manage"])
    user = make_user(google_sub="x", email="x@test.local", roles=[role])
    # Gọi service thực
    from app.services.department_service import DepartmentService
    DepartmentService().update_department(...)
```

### Mock service ngoài (Google OAuth / R2)

```python
def test_xxx(mock_external_services):
    # mock_external_services đã patch sẵn trong conftest
    # Dùng mock_external_services["presign_put"] để chỉnh return_value
    response = client.post(...)
```

## Lỗi thường gặp

| Lỗi | Nguyên nhân & sửa |
|---|---|
| `RuntimeError: Working outside of application context` | Dùng `app.app_context()` (auto qua fixture `app`) |
| `sqlite3.OperationalError: no such table` | Quên `create_all()` — kiểm tra fixture `app` trong conftest |
| Test pass local, fail CI | Có thể do timezone — `datetime.now(timezone.utc)` chuẩn hoá từ đầu |
| Coverage < 80% | Bổ sung test trong file `test_services_<name>.py` tương ứng |

## Thêm test mới

1. Tạo file `tests/test_services_<name>.py` (nếu chưa có service này).
2. Đặt tên function `test_<action>_<expected>` (theo convention pytest).
3. Nếu service có cấu trúc phức tạp → nhóm theo `class Test<MethodGroup>`.
4. Chạy `pytest tests/test_services_<name>.py -v` để verify.
5. Chạy `pytest --cov=app/services/<name>.py --cov-report=term-missing` để xem coverage cụ thể.
