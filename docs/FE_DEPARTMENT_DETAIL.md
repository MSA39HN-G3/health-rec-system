# Hướng dẫn API: Chi tiết Chuyên khoa (Department Detail)

> **Phiên bản: 1.3.0** — Bỏ field `head_doctor` / `head_doctor_id` trong response
> của Department (refactor 1a2b3c4d5e6f — staff quản lý tất cả bác sĩ, không còn
> khái niệm "trưởng khoa" gắn với 1 user/doctor cụ thể). Cột đã drop khỏi DB;
> role `doctor` đã bị xóa.
>
> Phiên bản 1.2.0 (CSV schema), 1.1.0 (export CSV cơ bản) và 1.0.1 (status/schedule) giữ nguyên.
>
> **Tài liệu liên quan**:
> - [`FE_DEPARTMENT.md`](./FE_DEPARTMENT.md) — API CRUD chuyên khoa hiện có.
> - [`FE_DOCTOR.md`](./FE_DOCTOR.md) — Model `Doctor`, danh sách trường liên quan.
> - [`FE_UPLOADS.md`](./FE_UPLOADS.md) — Quy ước upload ảnh qua R2 (`avatar_url` / `avatar_object_key`).
> - [`FE_AUTH_TOKEN.md`](./FE_AUTH_TOKEN.md) — Bearer token & 401/403 handling.

---

## 1. Bối cảnh

Màn chi tiết chuyên khoa hiện render **3 vùng dữ liệu**:

| Vùng | Nguồn dữ liệu hiện tại | Vấn đề |
|------|------------------------|--------|
| Header + Card "Thông tin cơ bản" | FE tự **scan tối đa 5 trang** `GET /api/v1/departments` để tìm 1 id | Tốn bandwidth, không scalable, không atomic |
| Stat "Số lượng bác sĩ" / "Bệnh nhân điều trị" | Chưa có → placeholder | — |
| Table "Danh sách bác sĩ trực thuộc" | Mock data | — |

**Mục tiêu của 2 endpoint**:
1. `GET /api/v1/departments/{id}` — trả 1 department.
2. `GET /api/v1/departments/{id}/doctors` — **gom `stats` + `doctors` list** vào 1 response (1 roundtrip, 1 transaction, snapshot nhất quán).

---

## 2. Endpoint 1 — `GET /api/v1/departments/{id}`

### 2.1. Request

```http
GET /api/v1/departments/{id}
Authorization: Bearer <access_token>
```

| Param | Vị trí | Kiểu | Bắt buộc | Mô tả |
|-------|--------|------|:--------:|-------|
| `id`  | path   | int  | ✅       | Khóa chính khoa (`> 0`) |

### 2.2. Response — 200 OK

Body bám sát envelope chung của hệ thống ([`FE_AUTH_TOKEN.md` §5](./FE_AUTH_TOKEN.md)):

```json
{
  "status": "success",
  "code": "200",
  "message": null,
  "data": {
    "id": 1,
    "code": "CK-001",
    "name": "Khoa Tim mạch",
    "location": "Tầng 3, Tòa nhà A",
    "avatar_url": "https://r2.example.com/department/abc.jpg?X-Amz-Expires=3600",
    "avatar_object_key": "department/abc.jpg",
    "description": "Chuyên điều trị các bệnh lý về tim mạch…",
    "keywords": ["đau ngực", "khó thở", "hồi hộp"],
    "conditions": ["tăng huyết áp", "nhồi máu cơ tim"],
    "techniques": [],
    "ai_metadata": null,
    "is_active": true,
    "created_at": "2025-08-12T03:21:45Z",
    "updated_at": "2026-01-04T08:11:00Z"
  },
  "meta": null
}
```

> ℹ️ Bắt đầu từ phiên bản 1.3.0, response **không còn** `head_doctor_id` /
> `head_doctor`. `is_active` là cờ do FE set qua POST/PATCH (xem
> [`FE_DEPARTMENT.md`](./FE_DEPARTMENT.md) mục 3 và 6).

### 2.3. Response — lỗi

| HTTP | `code` | Ý nghĩa |
|:----:|--------|----------|
| 401  | `AUTH_*` | Token thiếu/hết hạn → interceptor FE sẽ xử lý silent refresh hoặc đẩy về login. |
| 403  | `PERM_001` | User thiếu permission `department:manage`. |
| 404  | `DEPT_001` | Không tìm thấy khoa với `id` cho trước. |

```json
// 404
{
  "status": "error",
  "code": "DEPT_001",
  "message": "Không tìm thấy chuyên khoa với id = 999",
  "data": null,
  "meta": null
}
```

### 2.4. Gợi ý triển khai Python (FastAPI + SQLAlchemy)

```python
# app/api/v1/departments.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.department import Department
from app.common.responses import ok
from app.common.errors import NotFoundError
from app.common.auth import require_permission

router = APIRouter(prefix="/api/v1/departments", tags=["departments"])

@router.get("/{department_id}", response_model=None)
@require_permission("department:manage")
async def get_department(
    department_id: int,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Department)
        .where(Department.id == department_id)
    )
    result = await db.execute(stmt)
    department = result.scalar_one_or_none()
    if department is None:
        raise NotFoundError(
            code="DEPT_001",
            message=f"Không tìm thấy chuyên khoa với id = {department_id}",
        )
    return ok(data=department)
```

> **Lưu ý**: `avatar_url` là URL presigned GET do BE tự derive từ `avatar_object_key`
> (TTL ~1 giờ). Xem [`FE_UPLOADS.md`](./FE_UPLOADS.md) và
> [`FE_DEPARTMENT_AVATAR_UPLOAD.md`](./FE_DEPARTMENT_AVATAR_UPLOAD.md).

---

## 3. Endpoint 2 — `GET /api/v1/departments/{id}/doctors`

### 3.1. Lý do gộp `stats` + `doctors` vào 1 response

- **1 HTTP roundtrip** thay vì 2-3 (giảm latency ~50-70%).
- **1 transaction** → stats và list luôn đồng bộ tại cùng 1 snapshot.
- **Stats `treating_patients`** cần `JOIN appointments` → chạy chung pool, tránh race.
- FE hiện render 2 stat cards + 1 table phụ thuộc cùng `department_id` → đây là
  use-case điển hình của *compound endpoint* (xem Stripe, GitHub REST API).

### 3.2. Request

```http
GET /api/v1/departments/{id}/doctors?page=1&size=10&q=&qualification=
Authorization: Bearer <access_token>
```

| Param | Vị trí | Kiểu | Bắt buộc | Mặc định | Ràng buộc | Mô tả |
|-------|--------|------|:--------:|:--------:|-----------|-------|
| `id`             | path     | int    | ✅ | —    | `> 0`           | Khóa chính khoa |
| `page`           | query    | int    | ❌ | `1`  | `>= 1`          | Số trang (1-indexed) |
| `size`           | query    | int    | ❌ | `10` | `1 ≤ size ≤ 50` | Số bản ghi / trang |
| `q`              | query    | string | ❌ | `""` | `≤ 100 ký tự`   | Tìm theo `full_name` (case-insensitive, `ILIKE %q%`) |
| `qualification`  | query    | string | ❌ | `""` | `∈ {tiến_sĩ, thạc_sĩ, bác_sĩ_cki, bác_sĩ_nội_trú, ...}` | Lọc theo `title` |

> **Tham khảo thêm** (optional, có thể thêm nếu cần):
> `status` ∈ `{available, on_leave, in_session}` — lọc trạng thái làm việc.

### 3.3. Response — 200 OK

```json
{
  "status": "success",
  "code": "200",
  "message": null,
  "data": {
    "stats": {
      "total_doctors": 12,
      "active_doctors": 10,
      "inactive_doctors": 2,
      "treating_patients": 47
    },
    "doctors": [
      {
        "id": 1,
        "full_name": "Trần Thị Minh",
        "title": "Thạc sĩ, Bác sĩ CKI",
        "qualification": "Thạc sĩ",
        "experience_years": 12,
        "experience_display": "12 năm",
        "status": "available",
        "status_label": "ĐANG LÀM VIỆC",
        "schedule": {
          "days": ["T2", "T4", "T6"],
          "period": "Sáng",
          "summary": "T2, T4, T6 (Sáng)"
        },
        "avatar_url": "https://r2.example.com/doctor/xyz.jpg?X-Amz-Expires=3600",
        "is_accepting_new_patients": true
      }
    ]
  },
  "meta": {
    "totalPage": 2,
    "page": 1,
    "size": 10
  }
}
```

### 3.4. Định nghĩa các trường

#### `data.stats`

| Trường | Kiểu | Mô tả | Cách tính (gợi ý) |
|--------|------|-------|-------------------|
| `total_doctors`      | int | Tổng số bác sĩ thuộc khoa | `COUNT(*) WHERE department_id = :id` |
| `active_doctors`     | int | Số bác sĩ đang hoạt động | `COUNT(*) WHERE department_id = :id AND is_active = true` |
| `inactive_doctors`   | int | Số bác sĩ tạm ngưng | `total_doctors - active_doctors` |
| `treating_patients`  | int | Số bệnh nhân **đang được điều trị** bởi các bác sĩ trong khoa | `COUNT(DISTINCT patient_id) FROM appointments WHERE department_id = :id AND status IN ('checked_in', 'in_session') AND appointment_date = CURRENT_DATE` |

> **Lưu ý về `treating_patients`**:
> - Đếm theo **appointment chưa kết thúc** (`checked_in`, `in_session`) và **trong ngày** — khớp với ngữ nghĩa "đang điều trị".
> - Nếu hệ thống chưa có trạng thái `in_session`, fallback: `status = 'checked_in'`.
> - `DISTINCT patient_id` để 1 bệnh nhân có nhiều appointment chỉ tính 1 lần.

#### `data.doctors[]`

| Trường | Kiểu | Mô tả |
|--------|------|-------|
| `id`                       | int               | Khóa chính bác sĩ |
| `full_name`                | string            | Họ tên |
| `title`                    | string \| null    | Chức danh đầy đủ (vd "Thạc sĩ, Bác sĩ CKI") |
| `qualification`            | string \| null    | Trình độ ngắn gọn (vd "Thạc sĩ") — dùng cho filter chip |
| `experience_years`         | int \| null       | Số năm kinh nghiệm (raw) |
| `experience_display`       | string            | Format hiển thị ("12 năm") — FE có thể tự format, BE cung sẵn cho tiện |
| `status`                   | string enum       | `available` \| `on_leave` \| `in_session` |
| `status_label`             | string            | Nhãn tiếng Việt in hoa: "ĐANG LÀM VIỆC" / "ĐANG NGHỈ" / "CÓ LỊCH HẸN" |
| `schedule`                 | object \| null    | Lịch trực gần nhất (xem bảng dưới) |
| `avatar_url`               | string \| null    | URL presigned GET (TTL ~1h) |
| `is_accepting_new_patients`| bool              | Có nhận bệnh nhân mới không |

#### `data.doctors[].schedule`

| Trường | Kiểu | Mô tả |
|--------|------|-------|
| `days`    | string[] | Mã thứ trong tuần: `["T2", "T3", ..., "CN"]` |
| `period`  | string \| null | `"Sáng"` \| `"Chiều"` \| `"Cả ngày"` \| `null` (trực) |
| `summary` | string | Chuỗi hiển thị mặc định — FE dùng luôn không cần ghép: `"T2, T4, T6 (Sáng)"` |

> **Logic derive `status`** (gợi ý):
> - `in_session` = có appointment trong ngày với status `checked_in` hoặc `confirmed` chưa qua giờ kết thúc.
> - `on_leave` = có bản ghi nghỉ phép trong ngày (`doctor_leaves.start_date ≤ today ≤ end_date`).
> - `available` = mặc định còn lại.

### 3.5. Response — lỗi

| HTTP | `code` | Ý nghĩa |
|:----:|--------|----------|
| 401  | `AUTH_*` | Token thiếu/hết hạn. |
| 403  | `PERM_001` | Thiếu permission `department:manage`. |
| 404  | `DEPT_001` | Khoa không tồn tại. |
| 422  | `VAL_001` | Query param không hợp lệ (vd `size=0`, `page=-1`). |

### 3.6. Gợi ý triển khai Python (FastAPI + SQLAlchemy async)

```python
# app/api/v1/departments.py (bổ sung)
import asyncio
from datetime import date
from fastapi import Query
from sqlalchemy import select, func, case, and_, or_
from sqlalchemy.orm import selectinload

from app.models.doctor import Doctor
from app.models.appointment import Appointment
from app.models.doctor_schedule import DoctorSchedule

@router.get("/{department_id}/doctors", response_model=None)
@require_permission("department:manage")
async def list_department_doctors(
    department_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=50),
    q: str | None = Query(None, max_length=100),
    qualification: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    # 1) Kiểm tra khoa tồn tại (nếu không → 404)
    dept_exists = await db.scalar(
        select(Department.id).where(Department.id == department_id)
    )
    if dept_exists is None:
        raise NotFoundError(
            code="DEPT_001",
            message=f"Không tìm thấy chuyên khoa với id = {department_id}",
        )

    # 2) Query stats — 1 SQL, dùng COUNT + CASE
    stats_stmt = select(
        func.count(Doctor.id).label("total"),
        func.coalesce(
            func.sum(case((Doctor.is_active == True, 1), else_=0)), 0
        ).label("active"),
        func.count(func.distinct(Appointment.patient_id)).label("treating"),
    ).select_from(Doctor).outerjoin(
        Appointment,
        and_(
            Appointment.doctor_id == Doctor.id,
            Appointment.department_id == Doctor.department_id,
            Appointment.status.in_(["checked_in", "in_session"]),
            Appointment.appointment_date == date.today(),
        ),
    ).where(Doctor.department_id == department_id)

    # 3) Query doctors + count tổng (để tính totalPage)
    base_filter = [Doctor.department_id == department_id]
    if q:
        base_filter.append(Doctor.full_name.ilike(f"%{q}%"))
    if qualification:
        base_filter.append(Doctor.title.ilike(f"%{qualification}%"))

    count_stmt = select(func.count(Doctor.id)).where(*base_filter)
    doctors_stmt = (
        select(Doctor)
        .where(*base_filter)
        .order_by(Doctor.experience_years.desc().nullslast())
        .limit(size).offset((page - 1) * size)
    )

    # 4) Chạy song song 3 query (giảm latency)
    stats_res, count_res, doctors_res = await asyncio.gather(
        db.execute(stats_stmt),
        db.execute(count_stmt),
        db.execute(doctors_stmt),
    )
    stats_row = stats_res.one()
    total = count_res.scalar_one()
    doctors = doctors_res.scalars().all()

    # 5) Build response (DoctorSerializer.serialize_list)
    payload = {
        "stats": {
            "total_doctors": stats_row.total or 0,
            "active_doctors": stats_row.active or 0,
            "inactive_doctors": (stats_row.total or 0) - (stats_row.active or 0),
            "treating_patients": stats_row.treating or 0,
        },
        "doctors": [serialize_doctor_summary(d) for d in doctors],
    }
    meta = {"totalPage": (total + size - 1) // size, "page": page, "size": size}
    return ok(data=payload, meta=meta)


def serialize_doctor_summary(d: Doctor) -> dict:
    """Serialize tối thiểu cho table — không trả full model."""
    return {
        "id": d.id,
        "full_name": d.full_name,
        "title": d.title,
        "qualification": derive_qualification(d.title),  # helper nội bộ
        "experience_years": d.experience_years,
        "experience_display": (
            f"{d.experience_years} năm" if d.experience_years is not None else "—"
        ),
        "status": derive_status(d),                       # available/on_leave/in_session
        "status_label": STATUS_LABEL[derive_status(d)],
        "schedule": derive_schedule(d),                   # {days, period, summary}
        "avatar_url": presign_get(d.avatar_object_key),  # helper R2
        "is_accepting_new_patients": d.is_accepting_new_patients,
    }
```

### 3.7. Index đề xuất trên DB

Để `treating_patients` chạy nhanh khi scale:

```sql
CREATE INDEX IF NOT EXISTS idx_appointments_dept_status_date
  ON appointments (department_id, status, appointment_date);

CREATE INDEX IF NOT EXISTS idx_doctors_department_active
  ON doctors (department_id, is_active);

CREATE INDEX IF NOT EXISTS idx_doctor_schedules_doctor_date
  ON doctor_schedules (doctor_id, start_date);
```

---

## 4. Phân quyền

| Action | Permission | Roles mặc định |
|--------|------------|----------------|
| Xem chi tiết chuyên khoa (`GET /{id}`) | `department:manage` | `admin`, `staff` |
| Xem danh sách bác sĩ trực thuộc (`GET /{id}/doctors`) | `department:manage` | `admin`, `staff` |

> Nếu muốn mở rộng cho tài khoản "doctor" (xem bệnh nhân của mình) → thêm
> permission `department:read` hoặc cho phép filter `WHERE department_id IN (doctor.department_id)`
> ở service layer. Spec này **mặc định dùng `department:manage`** để nhất quán
> với các endpoint chuyên khoa khác.

---

## 5. Checklist triển khai BE

- [ ] Tạo Alembic migration nếu thêm bảng `doctor_schedule` / `doctor_leave`
      (chỉ cần nếu hệ thống chưa có schema lịch trực).
- [ ] Index `idx_appointments_dept_status_date` (xem §3.7).
- [ ] Serializer `serialize_doctor_summary` (mục tiêu < 5ms / bản ghi).
- [ ] Helper `presign_get(object_key)` — dùng lại helper R2 hiện có.
- [ ] Helper `derive_status(doctor)` + `STATUS_LABEL` enum.
- [ ] Helper `derive_schedule(doctor)` — chọn lịch gần nhất trong tuần này.
- [ ] Unit test cho `derive_status` (3 case: đang khám, nghỉ phép, rảnh).
- [ ] Test `treating_patients` với dữ liệu mẫu:
  - 0 appointment → `0`
  - 3 patient có 5 appointment cùng ngày → `3` (DISTINCT)
  - appointment đã `completed` → không đếm.
- [ ] Test load: 1000 bác sĩ / khoa, response time p95 < 300ms.

---

## 6. Tóm tắt 2 endpoints

| # | Method | Path | Permission | Trả về |
|---|:------:|------|------------|--------|
| 1 | `GET`  | `/api/v1/departments/{id}`              | `department:manage` | Object `Department` đầy đủ (không còn `head_doctor`) |
| 2 | `GET`  | `/api/v1/departments/{id}/doctors`      | `department:manage` | `{stats, doctors[]}` + `meta` phân trang |

**Hiệu quu**:
- Thay 3-5 HTTP roundtrip hiện tại bằng **2 roundtrip song song**.
- Stats + list luôn **đồng bộ snapshot** (1 transaction, 1 connection pool).
- Pagination **server-side** → FE không cần filter local.

---

## 5. Export CSV danh sách bác sĩ — `GET /api/v1/departments/{id}/doctors?format=csv`

> **Phiên bản: 1.1.0** — Thêm query `format=csv` để download file CSV chứa
> **toàn bộ** bác sĩ của khoa. Khi truyền `format=csv` sẽ **bỏ qua phân trang**:
> file chứa mọi bác sĩ khớp filter `q` / `qualification`.

### 5.1 Request

```http
GET /api/v1/departments/1/doctors?format=csv&q=Nguyen&qualification=Thac%20si HTTP/1.1
Authorization: Bearer <access_token>
```

| Query | Bắt buộc | Mặc định | Mô tả |
|-------|:--------:|:--------:|-------|
| `format` | không | `json` | `csv` để download file; giá trị khác (`xlsx`, `pdf`, …) → `422`. |
| `q` | không | `""` | Lọc theo `full_name` (ILIKE %q%). |
| `qualification` | không | `""` | Lọc theo `title` (ILIKE %x%). |

> **Phân trang bị bỏ qua**: `page` / `size` không có tác dụng khi `format=csv`.

### 5.2 Response — `200 OK` (file CSV)

- **Content-Type**: `text/csv; charset=utf-8`
- **Content-Disposition**: `attachment; filename="doctors_<code>_<timestamp>.csv"`
- **Body**: chuỗi CSV có **BOM UTF-8** để Excel tự nhận encoding tiếng Việt,
  phân tách cột bằng dấu `,`, escape theo RFC 4180.

Header `X-Export-Total-Rows` chứa số dòng dữ liệu (không tính header) để FE
hiển thị toast xác nhận.

### 5.3 Cột dữ liệu

Các cột được nhóm theo đúng phần model `Doctor`. Header có dạng
`"Tên tiếng Việt (key_en)"` để FE/PM tra lại mapping với JSON dễ dàng.

#### Nhóm 1 — Thông tin chung

| Cột (key) | Nhãn header | Nguồn | Format render |
|-----------|-------------|-------|--------------|
| `id` | `ID (id)` | `doctors.id` | số |
| `full_name` | `Họ tên (full_name)` | `doctors.full_name` | chuỗi |
| `title` | `Chức danh (title)` | `doctors.title` | chuỗi |
| `department_id` | `Mã khoa (department_id)` | `doctors.department_id` | số |
| `is_active` | `Đang hoạt động (is_active)` | `doctors.is_active` | `Có` / `Không` |

#### Nhóm 2 — Phần 1: Thông tin cá nhân

| Cột (key) | Nhãn header | Nguồn | Format render |
|-----------|-------------|-------|--------------|
| `phone` | `Số điện thoại (phone)` | `doctors.phone` | chuỗi |
| `email` | `Email (email)` | `doctors.email` | chuỗi |
| `date_of_birth` | `Ngày sinh (date_of_birth)` | `doctors.date_of_birth` | `dd/mm/yyyy` |
| `gender` | `Giới tính (gender)` | `doctors.gender` | `Nam` / `Nữ` / `Khác` |
| `address` | `Địa chỉ (address)` | `doctors.address` | chuỗi (escape theo RFC 4180) |

#### Nhóm 3 — Phần 2: Thông tin chuyên môn

| Cột (key) | Nhãn header | Nguồn | Format render |
|-----------|-------------|-------|--------------|
| `license_number` | `Số giấy phép hành nghề (license_number)` | `doctors.license_number` | chuỗi |
| `license_issue_date` | `Ngày cấp GPHN (license_issue_date)` | `doctors.license_issue_date` | `dd/mm/yyyy` |
| `license_expiry_date` | `Ngày hết hạn GPHN (license_expiry_date)` | `doctors.license_expiry_date` | `dd/mm/yyyy` |
| `specialization` | `Chuyên khoa chính (specialization)` | `doctors.specialization` | chuỗi |
| `sub_specializations` | `Chuyên khoa phụ (sub_specializations)` | `doctors.sub_specializations` | `"; "` joined |
| `education` | `Học vấn (education)` | `doctors.education` | `"; "` joined |
| `experience_years` | `Số năm kinh nghiệm (experience_years)` | `doctors.experience_years` | số |
| `training_institutions` | `Nơi đào tạo (training_institutions)` | `doctors.training_institutions` | `"; "` joined |

#### Nhóm 4 — Phần 5: Thông tin hành chính

| Cột (key) | Nhãn header | Nguồn | Format render |
|-----------|-------------|-------|--------------|
| `employment_type` | `Loại hợp đồng (employment_type)` | `doctors.employment_type` | `Toàn thời gian` / `Bán thời gian` / `Hợp đồng` |
| `hire_date` | `Ngày vào làm (hire_date)` | `doctors.hire_date` | `dd/mm/yyyy` |
| `contract_end_date` | `Ngày kết thúc HĐ (contract_end_date)` | `doctors.contract_end_date` | `dd/mm/yyyy` |
| `is_accepting_new_patients` | `Đang nhận bệnh nhân mới (is_accepting_new_patients)` | `doctors.is_accepting_new_patients` | `Có` / `Không` |

#### Nhóm 5 — Metadata (audit)

| Cột (key) | Nhãn header | Nguồn | Format render |
|-----------|-------------|-------|--------------|
| `created_at` | `Ngày tạo (created_at)` | `doctors.created_at` | `dd/mm/yyyy HH:MM` |
| `updated_at` | `Ngày cập nhật (updated_at)` | `doctors.updated_at` | `dd/mm/yyyy HH:MM` |

> **Trường bị bỏ** (so với `GET /doctors` JSON):
> - `avatar_url`, `avatar_object_key` — ảnh không phù hợp dạng bảng phẳng; FE nếu
>   cần hiển thị avatar có thể tự presign GET kèm `avatar_object_key`.
> - `documents`, `ratings`, `statistics` — quan hệ nặng.
> - `department` (object) — đã ngầm biết vì export theo khoa.

> **Quy ước render**:
> - `date` hiển thị `dd/mm/yyyy` (phù hợp VN); `datetime` thêm `HH:MM`.
> - `boolean` luôn render `"Có"` / `"Không"` (không phải `true`/`false`).
> - Enum `gender`, `employment_type` render nhãn tiếng Việt; nếu model thêm giá
>   trị mới chưa có mapping, BE fallback về mã thô để không mất dữ liệu.
> - Mảng (`sub_specializations`, `education`, `training_institutions`) join bằng
>   `"; "` để hiển thị gọn trong 1 ô.
> - `None` / giá trị thiếu render ô rỗng (không phải chuỗi `"None"`).

### 5.4 Response lỗi

| HTTP | `code` | Ý nghĩa |
|:----:|--------|----------|
| 401  | `AUTH_*` | Token thiếu/hết hạn. |
| 403  | `PERM_001` | Thiếu permission `department:manage`. |
| 404  | `DEPT_001` | Khoa không tồn tại. |
| 422  | `VAL_001` | `format` không hợp lệ (chỉ chấp nhận `json` / `csv`). |

### 5.5 Ví dụ

```bash
curl -X GET \
  -H "Authorization: Bearer <token>" \
  "https://api.example.com/api/v1/departments/1/doctors?format=csv" \
  -o doctors_cardio.csv
```

File `doctors_cardio.csv` mở được bằng Excel/LibreOffice với tiếng Việt hiển thị
đúng (do BOM UTF-8). Có thể lọc trước khi export:

```bash
# Chỉ export bác sĩ có tên chứa "Nguyễn"
curl -H "Authorization: Bearer <token>" \
  "https://api.example.com/api/v1/departments/1/doctors?format=csv&q=Nguyen" \
  -o cardio_nguyen.csv
```

### 5.6 Lưu ý triển khai FE

- Click "Export CSV" → mở URL trong tab mới hoặc dùng `<a download>` để tải về.
- Khi `q` / `qualification` trống → file chứa **toàn bộ** bác sĩ khoa (không
  giới hạn). Với khoa lớn (>5.000 bác sĩ) BE không giới hạn nhưng FE nên cân
  nhắc cảnh báo trước khi tải.
- BE đã set `Cache-Control: no-store` để đảm bảo mỗi lần export là dữ liệu
  mới nhất (không cache tại CDN/browser).

---

## 6. Tóm tắt 2 endpoints

| # | Method | Path | Permission | Trả về |
|---|:------:|------|------------|--------|
| 1 | `GET`  | `/api/v1/departments/{id}`              | `department:manage` | Object `Department` đầy đủ (không còn `head_doctor`) |
| 2 | `GET`  | `/api/v1/departments/{id}/doctors`      | `department:manage` | `{stats, doctors[]}` + `meta` phân trang; **`?format=csv` → file CSV** |

**Hiệu quả**:
- Thay 3-5 HTTP roundtrip hiện tại bằng **2 roundtrip song song**.
- Stats + list luôn **đồng bộ snapshot** (1 transaction, 1 connection pool).
- Pagination **server-side** → FE không cần filter local.
- Export CSV dùng chung endpoint, không cần roundtrip riêng.

---

## 7. Lịch sử thay đổi

| Version | Ngày | Thay đổi |
|---------|------|----------|
| **1.2.0** | Tổ chức lại schema CSV: nhóm cột theo phần model, header VI + key EN, bỏ avatar_url, date `dd/mm/yyyy`, bool/enum có nhãn tiếng Việt. |
| **1.1.0** | Bổ sung mục 5: export CSV danh sách bác sĩ của khoa qua `?format=csv` trên cùng endpoint. Bỏ qua phân trang, file có BOM UTF-8. |
| **1.0.1** | Cập nhật cho triển khai thực tế: bổ sung giải thích `status` (`available` / `on_leave` / `in_session`), `schedule` derive từ `doctor_schedules`. |
| 1.0.0   | 2026-07-12 | Bản đầu: 2 endpoint `GET /{id}` và `GET /{id}/doctors`. |