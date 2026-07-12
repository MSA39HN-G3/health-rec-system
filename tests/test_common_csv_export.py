"""Unit test cho helper `build_csv` (dùng cho export).

Mục tiêu: đảm bảo CSV chuẩn RFC 4180, escape đúng ký tự đặc biệt, có BOM
UTF-8 để Excel mở đúng tiếng Việt.
"""
from app.common.csv_export import build_csv


class TestBuildCsv:
    def test_starts_with_utf8_bom(self):
        out = build_csv(columns=["a"], header_labels=None, rows=[{"a": "x"}])
        assert out.startswith("\ufeff")

    def test_header_uses_labels(self):
        out = build_csv(
            columns=["name", "age"],
            header_labels={"name": "Họ tên", "age": "Tuổi"},
            rows=[],
        )
        assert "\ufeffHọ tên,Tuổi\r\n" in out

    def test_header_falls_back_to_column_name(self):
        out = build_csv(columns=["foo"], header_labels=None, rows=[])
        assert "\ufefffoo\r\n" in out

    def test_simple_rows(self):
        out = build_csv(
            columns=["id", "name"],
            header_labels=None,
            rows=[{"id": 1, "name": "An"}, {"id": 2, "name": "Bình"}],
        )
        assert out == "\ufeffid,name\r\n1,An\r\n2,Bình\r\n"

    def test_none_becomes_empty_string(self):
        out = build_csv(
            columns=["a", "b"],
            header_labels=None,
            rows=[{"a": None, "b": "x"}],
        )
        assert ",x\r\n" in out

    def test_list_joined_with_semicolon(self):
        out = build_csv(
            columns=["tags"],
            header_labels=None,
            rows=[{"tags": ["x", "y", "z"]}],
        )
        assert "x; y; z\r\n" in out

    def test_empty_list_renders_quoted_empty(self):
        # Chuỗi rỗng được CSV quote theo RFC 4180.
        out = build_csv(
            columns=["tags"],
            header_labels=None,
            rows=[{"tags": []}],
        )
        assert out == '\ufefftags\r\n""\r\n'

    def test_bool_normalized(self):
        out = build_csv(
            columns=["active"],
            header_labels=None,
            rows=[{"active": True}, {"active": False}],
        )
        assert "true\r\n" in out
        assert "false\r\n" in out

    def test_missing_key_renders_empty(self):
        out = build_csv(
            columns=["a", "b"],
            header_labels=None,
            rows=[{"a": "x"}],  # thiếu 'b'
        )
        assert "x,\r\n" in out

    def test_field_with_comma_is_quoted(self):
        out = build_csv(
            columns=["name"],
            header_labels=None,
            rows=[{"name": "Nguyễn, Văn A"}],
        )
        assert '"Nguyễn, Văn A"' in out

    def test_field_with_quote_is_escaped(self):
        out = build_csv(
            columns=["note"],
            header_labels=None,
            rows=[{"note": 'Anh nói "OK"'}],
        )
        assert '"Anh nói ""OK"""' in out

    def test_field_with_newline_is_quoted(self):
        out = build_csv(
            columns=["note"],
            header_labels=None,
            rows=[{"note": "dòng 1\ndòng 2"}],
        )
        assert '"dòng 1\ndòng 2"' in out

    def test_column_order_respected(self):
        out = build_csv(
            columns=["b", "a"],
            header_labels=None,
            rows=[{"a": 1, "b": 2}],
        )
        assert "b,a\r\n2,1\r\n" in out

    def test_vietnamese_text_preserved(self):
        out = build_csv(
            columns=["name"],
            header_labels=None,
            rows=[{"name": "Trần Thị Minh"}],
        )
        assert "Trần Thị Minh" in out