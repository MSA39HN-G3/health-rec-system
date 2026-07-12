"""Helper sinh file CSV chuẩn RFC 4180.

Mục đích: cung cấp 1 hàm duy nhất để các endpoint export dùng chung,
đảm bảo escape đúng (dấu phẩy, nháy đôi, xuống dòng) và encoding UTF-8
có BOM để Excel mở đúng tiếng Việt.

Tại sao tự viết thay vì dùng `csv.writer`?
  - `csv.writer` yêu cầu file handle; ta cần trả string để controller tự
    quyết định trả Response hay lưu R2.
  - BOM ở đầu giúp Excel auto-detect UTF-8 mà không cần mở qua Import.
"""
from __future__ import annotations

import io
import csv
from typing import Iterable, Mapping, Sequence

# BOM UTF-8 — Excel cần để hiển thị đúng tiếng Việt.
_UTF8_BOM = "\ufeff"


def build_csv(
    columns: Sequence[str],
    header_labels: Mapping[str, str] | None,
    rows: Iterable[Mapping[str, object]],
) -> str:
    """Sinh nội dung CSV từ danh sách cột + dữ liệu dict.

    Args:
        columns: thứ tự cột xuất hiện trong CSV (key dùng để lookup row).
        header_labels: map `column_key -> nhãn tiếng Việt` hiển thị ở header.
            Nếu None, header sẽ dùng nguyên `column_key`.
        rows: iterable các dict; thiếu key sẽ được fill bằng chuỗi rỗng.

    Returns:
        Chuỗi CSV đã bao gồm BOM, sẵn sàng ghi ra response.
    """
    buf = io.StringIO()
    # Dialect mặc định của `csv` tuân theo RFC 4180: phân tách bằng ",",
    # quote khi cần bằng `"`. Đủ cho use-case của ta.
    writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")

    labels = [header_labels.get(c, c) if header_labels else c for c in columns]
    writer.writerow(labels)

    for row in rows:
        writer.writerow([_format_cell(row.get(c)) for c in columns])

    return _UTF8_BOM + buf.getvalue()


def _format_cell(value):
    """Chuẩn hoá giá trị ô: None -> '', list -> '; '-joined, datetime -> iso."""
    if value is None:
        return ""
    if isinstance(value, list):
        return "; ".join(str(v) for v in value)
    if isinstance(value, bool):
        return "true" if value else "false"
    return value