# decorators.py  —— Pure standard library, ready to run
import time, random, threading
from functools import wraps
from collections import deque

class DynamicRateLimiter:
    """Token bucket + dynamic rate adjustment (tokens/sec)."""
    def __init__(self, rps: float, capacity: int = 100):
        self.rate, self.capacity = float(rps), capacity
        self.tokens, self.ts = capacity, time.time()
        self.lock = threading.Lock()

    def set_rate(self, rps: float):
        """Dynamically adjust the rate at runtime."""
        with self.lock:
            self.rate = max(0.001, float(rps))

    def acquire(self, n: int = 1):
        """Acquire n tokens; block until available."""
        while True:
            with self.lock:
                now = time.time()
                # Refill tokens based on elapsed time
                self.tokens = min(self.capacity, self.tokens + (now - self.ts) * self.rate)
                self.ts = now
                if self.tokens >= n:
                    self.tokens -= n
                    return
            # Sleep briefly with jitter to reduce contention
            time.sleep(0.01 + random.random() * 0.02)

class CircuitBreaker:
    """Simple circuit breaker: open after N failures, reset after timeout."""
    def __init__(self, fail_threshold=5, reset_after=30):
        self.fail_threshold, self.reset_after = fail_threshold, reset_after
        self.fail_count, self.open_until = 0, 0

    def before(self):
        if time.time() < self.open_until:
            raise RuntimeError("circuit-open")

    def success(self): 
        self.fail_count = 0

    def failure(self):
        self.fail_count += 1
        if self.fail_count >= self.fail_threshold:
            self.open_until, self.fail_count = time.time() + self.reset_after, 0

dead_letter = deque(maxlen=10000)  # Dead-letter queue for failed requests

def resilient(rate: DynamicRateLimiter, breaker: CircuitBreaker,
              max_attempts=6, base_backoff=0.3):
    """Retry decorator: dynamic rate limit + exponential backoff + dead-letter queue + circuit breaker."""
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kw):
            for k in range(1, max_attempts+1):
                try:
                    breaker.before()
                    rate.acquire()
                    resp = fn(*args, **kw)   # resp = {'status', 'headers', 'data'}
                    # Adjust rate dynamically if server sends new limit
                    new_rps = resp.get('headers', {}).get('X-Rate-Limit-RPS')
                    if new_rps:
                        rate.set_rate(float(new_rps))
                    if resp.get('status', 200) == 200:
                        breaker.success()
                        return resp['data']
                    if resp['status'] in (429, 500, 502, 503, 504):
                        raise RuntimeError("retryable")
                    # Non-retryable error → send to dead-letter queue
                    dead_letter.append({'args': args, 'kw': kw, 'reason': f"status-{resp['status']}"})
                    raise
                except Exception as e:
                    breaker.failure()
                    if "retryable" not in str(e) or k == max_attempts:
                        dead_letter.append({'args': args, 'kw': kw, 'reason': str(e)})
                        raise
                    # Exponential backoff with jitter
                    time.sleep(base_backoff * (2**(k-1)) * (0.9 + 0.2*random.random()))
        return wrapper
    return deco

# ---- Demo: simulate API returning 429 every 20th request and sending new rate (10 rps)
rl = DynamicRateLimiter(100.0, 200)
cb = CircuitBreaker(5, 15)

@resilient(rl, cb)
def fetch_pushshift(params):
    """
    Fake response generator for demo:
    - Normally returns status=200
    - Every 20th call, return 429 with a new rate limit (10 rps)
    In practice, replace with: requests.get(url, params=..., timeout=...)
    """
    fetch_pushshift.c = getattr(fetch_pushshift, "c", 0) + 1
    if fetch_pushshift.c % 20 == 0:
        return {'status': 429, 'headers': {'X-Rate-Limit-RPS': '10'}, 'data': None}
    return {'status': 200, 'headers': {}, 'data': {'hits': 100, 'params': params}}

if __name__ == "__main__":
    ok = 0
    for i in range(60):
        try:
            fetch_pushshift({'q': i})
            ok += 1
        except Exception as e:
            print("ERR:", e)
    print("success:", ok, "dead_letter:", len(dead_letter))
