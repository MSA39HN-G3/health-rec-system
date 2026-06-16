"""Điểm khởi chạy ứng dụng cho môi trường phát triển.

Nạp biến môi trường từ .env rồi tạo app qua factory.
Chạy: python run.py  (hoặc dùng: flask --app run run)
"""
from dotenv import load_dotenv

load_dotenv()

from app import create_app  # noqa: E402  (load_dotenv phải chạy trước khi đọc config)

app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
