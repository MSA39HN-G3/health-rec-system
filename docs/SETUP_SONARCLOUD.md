# Hướng dẫn thiết lập CI/CD với SonarCloud + GitHub Actions

> **Đối tượng**: dự án Python/Flask (`health-rec-system`) đẩy lên GitHub.
> **Mục tiêu**: mở Pull Request → tự động quét Sonar → chỉ cho merge khi
> **Quality Gate PASSED**.

---

## 1. Tổng quan luồng hoạt động

```
PR mở / đẩy thêm commit
    └─> GitHub Actions chạy workflow ".github/workflows/sonar.yml"
            └─ sonar-scanner phân tích code → upload lên SonarCloud
                    └─ SonarCloud đặt status check "SonarCloud/quality-gate"
                            └─ Branch Protection Rule kiểm tra
                                  Status check phải = SUCCESS → mới hiển nút Merge
```

> **Lưu ý**: workflow **không chạy test** và **không upload coverage**. Mọi metric
> liên quan đến coverage (`coverage.xml`, `pytest`, …) đã được lược bỏ hoàn toàn
> để tránh fail Quality Gate vì lý do ngoài ý muốn.

Vai trò 3 thành phần:

| Thành phần | Việc cần làm |
|---|---|
| SonarCloud | Lưu trữ project, đánh giá code, đặt status check |
| GitHub Actions | Chạy test + gọi sonar-scanner mỗi khi có PR |
| GitHub Branch Protection | Khóa nút Merge nếu Quality Gate fail |

---

## 2. Chuẩn bị

Bạn cần trước khi làm các bước bên dưới:

- Repo đã push lên GitHub (đã có 1 commit ít nhất).
- Tài khoản GitHub có quyền **Admin** trên repo đó.
- Tài khoản SonarCloud (tạo miễn phí tại https://sonarcloud.io), **không** dùng test/coverage.

---

## 3. Bước 1 — Đăng ký project trên SonarCloud

1. Vào https://sonarcloud.io, bấm **Sign in with GitHub** → ủy quyền cho SonarCloud.
2. Sau khi login → bấm **+** ở góc trên phải → **Analyze new project**.
3. Chọn **From GitHub** → tick vào `health-rec-system` → **Set Up**.
4. Ở màn hình chọn phương thức phân tích → chọn **With GitHub Actions** (khuyến nghị) → **Next**.
5. SonarCloud sinh sẵn file mẫu, nhưng trong hướng dẫn này mình dùng file cấu hình riêng cho khớp repo Python, nên bạn **đóng popup đó**, chuyển sang bước tiếp theo.

Ghi nhớ 2 giá trị (cần trong bước 4):

| Giá trị | Lấy ở đâu | Ví dụ |
|---|---|---|
| **Organization key** | SonarCloud → góc trên phải → nhấn avatar → **My Account** → tab **Organizations** | `ppr501-fpt` |
| **Project key** | Trang project vừa tạo → **Administration** → **Project Information** | `ppr501-fpt_health-rec-system` |

> Quy ước default của SonarCloud: `projectKey = <organizationKey>_<repoName>`.

---

## 4. Bước 2 — Tạo Sonar Token

Token này cho phép GitHub Actions đẩy kết quả quét lên SonarCloud.

1. Vào https://sonarcloud.io/account/security.
2. Kéo xuống phần **Generate Tokens**:
   - **Name**: `github-actions-ppr501`
   - **Type**: **User Token** (hoặc **Project Analysis Token** nếu muốn giới hạn quyền).
3. Bấm **Generate** → **copy token** ngay. Token chỉ hiện đúng 1 lần.

---

## 5. Bước 3 — Thêm secrets vào GitHub

1. Trên GitHub → vào repo `health-rec-system`.
2. **Settings** → **Secrets and variables** → **Actions**.
3. Tab **Secrets** → **New repository secret**:

| Name | Value |
|---|---|
| `SONAR_TOKEN` | dán token vừa copy ở bước 4 |

4. Bấm **Add secret**.

> Organization key, project key không nhạy cảm → mình hard-code trong file config bước 6.

---

## 6. Bước 4 — Tạo file cấu hình SonarScanner

Tạo file `sonar-project.properties` ở **root repo** (ngang hàng `requirements.txt`).

```properties
# sonar-project.properties - top-level

# Trùng Organization key và Project key lấy ở bước 3.
# Khi tạo mới project, SonarCloud đặt default theo format:
#     <orgKey>_<repoName>
sonar.projectKey=<đổi thành project key của bạn>
sonar.organization=<đổi thành organization key của bạn>

# Phạm vi phân tích
sonar.sources=app
sonar.tests=tests

# Loại trừ những thư mục không phải code production
sonar.exclusions=**/migrations/**,**/__pycache__/**,**/.venv/**,**/scripts/**

sonar.language=py
sonar.sourceEncoding=UTF-8

# Không dùng coverage / test trong thiết lập này — đã bỏ.
```

Commit file này lên default branch (thường là `main`) trước khi setup workflow.

> File này đã được tạo sẵn trong repo, bạn chỉ cần thay 2 giá trị
> `sonar.projectKey` và `sonar.organization` là chạy được.

---

## 7. Bước 5 — Tạo GitHub Actions workflow

Tạo file `.github/workflows/sonar.yml` ở **root repo**.

```yaml
# .github/workflows/sonar.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch:        # Cho phép "Run workflow" thủ công từ tab Actions (debug).

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true   # PR mới commit → huỷ run cũ

jobs:
  sonar:
    # Workflow này KHÔNG chạy test, KHÔNG cài dependencies, KHÔNG đẩy coverage.
    # Nó chỉ clone source và chạy sonar-scanner để phân tích code.
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0     # Sonar cần full git history để blame

      - name: SonarCloud Scan
        uses: sonarsource/sonarqube-scan-action@v2
        env:
          SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
        # Không truyền thêm tham số, action sẽ tự đọc sonar-project.properties.
```

> File này đã được tạo sẵn trong repo, bạn không cần sửa gì.

### Nếu sau này muốn bật lại test + coverage

Đổi `jobs.sonar.steps` thành bản đầy đủ (cài Python, cài `pytest`, chạy
`coverage xml -i`), rồi bật dòng `sonar.python.coverage.reportPaths=coverage.xml`
trong `sonar-project.properties`. Section này chỉ là gợi ý, không bắt buộc.

---

## 8. Bước 6 — Chạy workflow lần đầu (để SonarCloud xuất hiện trong GitHub)

Branch Protection cần chọn status check — mà status check chỉ xuất hiện ở GitHub
**sau khi workflow chạy thành công ít nhất 1 lần**.

Thực hiện:

1. Commit 2 file `sonar-project.properties` + `.github/workflows/sonar.yml` lên branch `main`.
2. Push lên GitHub.
3. Vào tab **Actions** của repo → mở workflow **CI / sonar** vừa chạy → đợi PASSED
   (khoảng 1–2 phút).
4. Mở **Pull Request test** (vd đổi 1 dòng trong README):
   - Bấm **Create PR** → tab **Checks** sẽ thấy status `SonarCloud/quality-gate`
     được liệt kê (kể cả khi trạng thái là "Passed" hay "Failed").

Nếu không thấy status check sonar → đợi thêm 1 phút, refresh trang PR.

---

## 9. Bước 7 — Cấu hình Quality Gate (khuyến nghị)

Đây là **bộ quy tắc** quyết định PASSED hay FAILED cho status check.

### 9.1 Dùng Quality Gate mặc định "Sonar way"

- Vào SonarCloud → chọn project → **Administration** → **Quality Gate**.
- Mặc định đã áp dụng **Sonar way**. Bạn có thể dùng luôn.

### 9.2 (Khuyến nghị) Tạo custom gate KHÔNG yêu cầu coverage

Vì đã bỏ coverage, không nên đưa metric "Coverage on new code" vào gate. Một bộ
gate phù hợp cho project này — tại **Quality Gates** → **Create** → đặt tên
`health-rec-system-strict`:

| Metric | Operator | Value |
|---|---|---|
| Duplicated Lines (%) on New Code | is greater than | **3%** |
| Maintainability Rating on New Code | is worse than | **A** |
| Reliability Rating on New Code | is worse than | **A** |
| Security Rating on New Code | is worse than | **A** |

Quan trọng: giá trị áp dụng trên **New Code** (code thay đổi trong PR), không phải
toàn bộ repo. Tránh việc gate fail vì nợ kỹ thuật cũ.

Sau khi tạo → vào project → **Administration** → **Quality Gate** → chọn
`health-rec-system-strict` → **Set as default**.

Quan trọng: giá trị áp dụng trên **New Code** (code thay đổi trong PR), không phải
toàn bộ repo. Tránh việc gate fail vì nợ kỹ thuật cũ.

Sau khi tạo → vào project → **Administration** → **Quality Gate** → chọn
`health-rec-system-strict` → **Set as default**.

---

## 10. Bước 8 — Bật Branch Protection (BẮT BUỘC)

Đây là bước khóa nút **Merge** khi Quality Gate fail.

Repo GitHub → **Settings** → **Branches** → **Add branch protection rule**:

| Setting | Bật / Value |
|---|---|
| Branch name pattern | `main` |
| **Require a pull request before merging** | ✅ |
| **Require approvals** | ✅ **1** |
| **Dismiss stale pull request approvals** | ✅ |
| **Require status checks to pass before merging** | ✅ |
| **Require branches to be up to date before merging** | ✅ |
| **Require conversation resolution** | ✅ |
| **Do not allow bypassing the above settings** | ✅ |
| Allow force pushes | ⬜ (giữ tắt) |
| Allow deletions | ⬜ (giữ tắt) |

Trong ô **Search for status checks...** gõ:

```
SonarCloud/quality-gate
```

→ tick chọn **`SonarCloud/quality-gate`** (status check do Sonar tạo ra).
Sau đó **Save changes**.

> Nếu không thấy `SonarCloud/quality-gate` trong dropdown → quay lại bước 8
> để chạy workflow ít nhất 1 lần trước.

---

## 11. Bước 9 — Verify từ đầu đến cuối

Tạo Pull Request test (đổi 1 dòng README):

1. Vào tab **Pull requests** → **New pull request**.
2. Quan sát:
   - **Bên phải**: tab "Checks" → `CI / build` chạy, có `SonarCloud/quality-gate`
     check kết quả PASSED.
   - **Bên dưới**: SonarCloud tự động comment vào PR:
     > "## SonarCloud Quality Gate: Passed"
3. Nút **Merge** sẽ chỉ enable khi:
   - Quality Gate: ✅ Passed
   - Branch up-to-date với `main`: ✅
   - Có ≥ 1 approval: ✅
   - Conversations resolved: ✅

Để test **luồng fail**, sửa 1 hàm có chủ ý để Sonar báo bug (vd chia cho biến có
thể bằng 0) → push → PR sẽ chuyển status đỏ, nút Merge bị disable.

---

## 12. Cấu trúc file đã tạo trong repo

```
.
├── .github/
│   └── workflows/
│       └── sonar.yml                  ← workflow CI
├── sonar-project.properties           ← config SonarScanner
├── (root)
├── app/                                  ← code production
├── docs/
│   └── SETUP_SONARCLOUD.md            ← file hướng dẫn bạn đang đọc
└── ...
```

---

## 13. Best practice cho dự án Python

| Vấn đề | Giải pháp |
|---|---|
| Chưa có test / chưa bật coverage | Dùng gate chỉ dựa trên Maintainability/Reliability/Security + Duplications (đã làm sẵn ở bước 7.2) |
| `migrations/` (Alembic) không phải code production | Đã exclude qua `sonar.exclusions` |
| Repo lớn nhưng chỉ có 1 môi trường | Free plan SonarCloud (10k LOC) đủ dùng |
| Bypass rule khi khẩn cấp | Tắt "Allow force pushes" để không ai merge nếu fail |
| PR có nhiều commit | Dùng **Squash and merge** để gộp, giữ history gọn |
| Default branch chưa bao giờ được quét | Sonar sẽ tự phân tích khi push lần đầu, lấy baseline |
| Chỉ muốn scan PR, không scan main | Thêm condition `if: github.event_name == 'pull_request'` quanh step SonarScan |

### Mẹo giữ gate ổn định theo thời gian

- Giữ gate chỉ ở metric rating A–E và duplication, **bỏ qua coverage** để tránh
  fail vì lý do ngoài ý muốn.
- Khi đội đã có test ổn định (≥ 60% line coverage trên new code) → bật lại
  coverage bằng cách thêm step test + dòng `sonar.python.coverage.reportPaths`.
- Tạo `docs/CONTRIBUTING.md` nhắc team: "PR phải pass Quality Gate ở A trước khi
  mời review".

---

## 14. Troubleshooting nhanh

| Triệu chứng | Nguyên nhân & cách xử lý |
|---|---|
| SonarCloud comment "no new issues" nhưng Quality Gate FAILED | Rating tổng quát (A..E) chưa được scan lại default branch — vào **Administration → Background Tasks**, bấm **Cancel** task cũ, push lại 1 commit nhỏ |
| Workflow chạy xong nhưng nút Merge vẫn xanh → ấn vẫn merge được | Branch Protection Rule chưa tick đúng `SonarCloud/quality-gate` — vào lại **Settings → Branches → Edit rule** |
| `SONAR_TOKEN` secret không nhận | Repo fork không inherit secret, phải set lại ở fork |
| Status check sonar không hiện ở dropdown | Workflow chưa từng chạy thành công trên PR — tạo 1 PR test, đợi nó chạy xong |
| Scan báo lỗi "Project not found" | `sonar.projectKey` sai (thường thiếu `_` giữa org và repo) — copy lại từ trang project SonarCloud |

---

## 15. Checklist hoàn tất

- [x] Tài khoản SonarCloud đăng ký bằng GitHub.
- [x] Organization key và Project key đã ghi ra giấy.
- [x] Token sinh ra và lưu trong GitHub secret `SONAR_TOKEN`.
- [x] File `sonar-project.properties` đã chỉnh `projectKey` + `organization`.
- [x] File `.github/workflows/sonar.yml` đã commit.
- [x] Workflow chạy thành công trên PR test.
- [x] Quality Gate đã cấu hình (Sonar way hoặc custom).
- [x] Branch Protection Rule đã tick `SonarCloud/quality-gate`.
- [x] Test bằng cách tạo PR test → nút Merge bị disable khi Quality Gate fail.

Khi tất cả tick → project đã đạt chuẩn **"Pull Request → quét sonar → pass mới merge"**.
