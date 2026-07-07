# Curl Commands - Health Record System API

Base URL: `http://localhost:5000`

> ⚠️ **Lưu ý**: Thay `$TOKEN` bằng access token thực từ đăng nhập Google. Token có format: `Bearer <JWT_token>`

---

## 1. Authentication Endpoints

### 1.1 Health Check
```bash
curl -X GET http://localhost:5000/health
```

### 1.2 Lấy URL đăng nhập Google
```bash
# STATE là chuỗi ngẫu nhiên 8-128 ký tự, BE sẽ kiểm tra để chống CSRF
curl -X GET "http://localhost:5000/api/v1/auth/google/url?state=random_state_12345"
```

### 1.3 Google OAuth Callback (sau khi user chọn tài khoản Google)
```bash
curl -X POST http://localhost:5000/api/v1/auth/google/callback \
  -H "Content-Type: application/json" \
  -d '{
    "authorization_code": "4/0AX4XfWg...",
    "state": "random_state_12345"
  }'
```
**Response:**
```json
{
  "success": true,
  "data": {
    "user": {
      "id": 1,
      "email": "user@gmail.com",
      "full_name": "John Doe",
      "roles": ["user"]
    },
    "is_new_user": false,
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "Bearer",
    "expires_at": "2026-07-07T19:30:00"
  },
  "message": "Đăng nhập thành công."
}
```

### 1.4 Lấy thông tin user hiện tại
```bash
curl -X GET http://localhost:5000/api/v1/auth/me \
  -H "Authorization: Bearer $TOKEN"
```

### 1.5 Logout
```bash
curl -X POST http://localhost:5000/api/v1/auth/logout \
  -H "Authorization: Bearer $TOKEN"
```

---

## 2. Patient Management Endpoints

> ⚠️ Tất cả endpoint dưới đây yêu cầu:
> - Header: `Authorization: Bearer $TOKEN`
> - Permission: `USER_READ` (list/get), `USER_MANAGE` (create/update)

### 2.1 Danh sách bệnh nhân (phân trang)
```bash
curl -X GET "http://localhost:5000/api/v1/patients?page=1&size=20" \
  -H "Authorization: Bearer $TOKEN"
```

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "full_name": "Nguyễn Văn A",
      "date_of_birth": "1990-01-15",
      "gender": "male",
      "phone": "0912345678",
      "email": "patient@example.com",
      "address": "123 Nguyen Hue St, HCMC"
    }
  ],
  "pagination": {
    "page": 1,
    "size": 20,
    "total": 50
  }
}
```

### 2.2 Tạo bệnh nhân mới
```bash
curl -X POST http://localhost:5000/api/v1/patients \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "Trần Thị B",
    "date_of_birth": "1995-05-20",
    "gender": "female",
    "phone": "0987654321",
    "email": "patient2@example.com",
    "address": "456 Tran Hung Dao St, Hanoi"
  }'
```

### 2.3 Lấy chi tiết bệnh nhân
```bash
curl -X GET http://localhost:5000/api/v1/patients/1 \
  -H "Authorization: Bearer $TOKEN"
```

### 2.4 Cập nhật bệnh nhân
```bash
curl -X PATCH http://localhost:5000/api/v1/patients/1 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "phone": "0911111111",
    "address": "789 New Address St, Da Nang"
  }'
```

---

## 3. Health Records Endpoints

> ⚠️ Yêu cầu:
> - Header: `Authorization: Bearer $TOKEN`
> - Permission: `RECORD_READ` (list), `RECORD_WRITE` (create)

### 3.1 Danh sách hồ sơ sức khỏe của bệnh nhân
```bash
curl -X GET "http://localhost:5000/api/v1/patients/1/records?page=1&size=20" \
  -H "Authorization: Bearer $TOKEN"
```

### 3.2 Tạo hồ sơ sức khỏe
```bash
curl -X POST http://localhost:5000/api/v1/patients/1/records \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Khám tổng quát",
    "visit_date": "2026-07-07",
    "doctor_id": 1,
    "department_id": 2,
    "notes": "Tình trạng bệnh nhân ổn định",
    "diagnosis": "Cảm cúm",
    "treatment": "Dùng thuốc hạ sốt và antibiotics"
  }'
```

---

## 4. Department Endpoints

### 4.1 Danh sách phòng khám/khoa
```bash
curl -X GET "http://localhost:5000/api/v1/departments?page=1&size=20" \
  -H "Authorization: Bearer $TOKEN"
```

### 4.2 Tạo phòng khám mới
```bash
curl -X POST http://localhost:5000/api/v1/departments \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Khoa Nội",
    "description": "Khoa Nội tổng hợp"
  }'
```

---

## 5. Doctor Endpoints

### 5.1 Danh sách bác sĩ
```bash
curl -X GET "http://localhost:5000/api/v1/doctors?page=1&size=20" \
  -H "Authorization: Bearer $TOKEN"
```

### 5.2 Tạo bác sĩ mới
```bash
curl -X POST http://localhost:5000/api/v1/doctors \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "Dr. Lê Văn C",
    "specialization": "Cardiology",
    "department_id": 1,
    "phone": "0912345678",
    "email": "doctor@hospital.com"
  }'
```

---

## 6. Symptoms Endpoints

### 6.1 Danh sách triệu chứng
```bash
curl -X GET "http://localhost:5000/api/v1/symptoms?page=1&size=20" \
  -H "Authorization: Bearer $TOKEN"
```

### 6.2 Tạo triệu chứng mới
```bash
curl -X POST http://localhost:5000/api/v1/symptoms \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Sốt cao",
    "description": "Nhiệt độ cơ thể cao hơn 38°C"
  }'
```

---

## 7. File Upload Endpoints

### 7.1 Upload file (ảnh, tài liệu)
```bash
curl -X POST http://localhost:5000/api/v1/uploads \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/file.pdf" \
  -F "type=document"
```

---

## 8. Admin Endpoints

### 8.1 Dashboard thống kê
```bash
curl -X GET http://localhost:5000/api/v1/admin/statistics \
  -H "Authorization: Bearer $TOKEN"
```

---

## Hữu ích khi Debug

### Lưu response vào file
```bash
curl -X GET http://localhost:5000/api/v1/patients \
  -H "Authorization: Bearer $TOKEN" \
  -o response.json
```

### Xem chi tiết request/response (header, timing, etc.)
```bash
curl -X GET http://localhost:5000/api/v1/patients \
  -H "Authorization: Bearer $TOKEN" \
  -v
```

### Định dạng JSON output (sử dụng jq nếu cài)
```bash
curl -X GET http://localhost:5000/api/v1/patients \
  -H "Authorization: Bearer $TOKEN" | jq
```

### Thêm query string parameters
```bash
curl -X GET "http://localhost:5000/api/v1/patients?lang=vi&page=2&size=10" \
  -H "Authorization: Bearer $TOKEN"
```

### Test với custom headers
```bash
curl -X GET http://localhost:5000/api/v1/patients \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept-Language: vi" \
  -H "Accept: application/json"
```

---

## Cấu trúc Response

### Success Response
```json
{
  "success": true,
  "data": { /* Dữ liệu trả về */ },
  "message": "Hoạt động thành công"
}
```

### Error Response
```json
{
  "success": false,
  "error": {
    "code": 401,
    "message": "Token không hợp lệ",
    "details": { /* Chi tiết lỗi */ }
  }
}
```

### Paginated Response
```json
{
  "success": true,
  "data": [ /* Danh sách items */ ],
  "pagination": {
    "page": 1,
    "size": 20,
    "total": 100
  }
}
```

---

## Lưu ý

- 📌 **Access Token**: Lấy từ Google OAuth callback, format: `Bearer <JWT_token>`
- ⏰ **Expiration**: Token hết hạn sau 1 giờ (hoặc theo `JWT_EXPIRES` trong config)
- 🔒 **Permissions**: Mỗi endpoint có yêu cầu quyền riêng (xem `Permission` enum)
- 🌐 **Multi-language**: Thêm `?lang=vi` hoặc `?lang=en` để chọn ngôn ngữ response
- 📝 **Validation**: Server kiểm tra input body, nếu sai sẽ trả lỗi 400 với chi tiết lỗi

