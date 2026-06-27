"""Cài đặt thuật toán Token Bucket cho rate limit.

Ý tưởng: mỗi client giữ một "giỏ" token, sức chứa tối đa = `capacity`.
Mỗi request tiêu tốn 1 token. Token được hồi đều theo thời gian với tốc độ
`refill_rate` token/giây. Nhờ vậy:
  - Cho phép bùng nổ (burst) tối đa `capacity` request liên tiếp.
  - Sau đó request bị giới hạn ở tốc độ ổn định `refill_rate`/giây.

Bản này lưu trạng thái trong bộ nhớ tiến trình (có khóa để an toàn đa luồng).
Khi triển khai nhiều worker/instance ở production, nên chuyển sang backend dùng
chung (vd Redis) để chia sẻ trạng thái giữa các tiến trình.
"""
import threading
import time


class TokenBucketLimiter:
    def __init__(self, time_func=time.monotonic):
        # key -> [tokens hiện có, mốc thời gian cập nhật gần nhất]
        self._buckets = {}
        self._lock = threading.Lock()
        self._time = time_func

    def hit(self, key, capacity, refill_rate, cost=1.0):
        """Tiêu thụ `cost` token cho `key`.

        Trả về (allowed, remaining, retry_after):
          - allowed:     True nếu còn đủ token (được phép), ngược lại False.
          - remaining:   số token còn lại (đã làm tròn xuống số nguyên).
          - retry_after: số giây cần chờ để có đủ token (chỉ ý nghĩa khi bị chặn).
        """
        now = self._time()
        with self._lock:
            entry = self._buckets.get(key)
            if entry is None:
                tokens, last = float(capacity), now
            else:
                tokens, last = entry
                # Hồi token theo thời gian đã trôi qua, không vượt quá capacity.
                tokens = min(capacity, tokens + (now - last) * refill_rate)
                last = now

            if tokens >= cost:
                tokens -= cost
                self._buckets[key] = [tokens, last]
                return True, int(tokens), 0.0

            self._buckets[key] = [tokens, last]
            retry_after = (cost - tokens) / refill_rate if refill_rate > 0 else None
            return False, int(tokens), retry_after
