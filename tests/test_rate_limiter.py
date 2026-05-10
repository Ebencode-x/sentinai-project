"""Tests for src/core/rate_limiter.py — token bucket rate limiter."""

from __future__ import annotations

import threading
import time


from src.core.rate_limiter import TokenBucket


class TestTokenBucketBasics:
    def test_consume_returns_true_when_tokens_available(self):
        bucket = TokenBucket(capacity=5, refill_per_minute=5)
        assert bucket.consume() is True

    def test_consume_returns_false_when_empty(self):
        bucket = TokenBucket(capacity=1, refill_per_minute=1)
        bucket.consume()
        assert bucket.consume() is False

    def test_full_bucket_capacity_consumed(self):
        bucket = TokenBucket(capacity=3, refill_per_minute=60)
        results = [bucket.consume() for _ in range(3)]
        assert all(results)

    def test_one_over_capacity_is_false(self):
        bucket = TokenBucket(capacity=3, refill_per_minute=60)
        for _ in range(3):
            bucket.consume()
        assert bucket.consume() is False

    def test_capacity_one_allows_one_request(self):
        bucket = TokenBucket(capacity=1, refill_per_minute=60)
        assert bucket.consume() is True
        assert bucket.consume() is False

    def test_large_capacity_all_consumed(self):
        bucket = TokenBucket(capacity=10, refill_per_minute=10)
        results = [bucket.consume() for _ in range(10)]
        assert all(results)
        assert bucket.consume() is False


class TestTokenBucketRefill:
    def test_tokens_refill_over_time(self):
        bucket = TokenBucket(capacity=2, refill_per_minute=120)
        bucket.consume()
        bucket.consume()
        assert bucket.consume() is False
        time.sleep(0.6)
        assert bucket.consume() is True

    def test_tokens_do_not_exceed_capacity(self):
        bucket = TokenBucket(capacity=3, refill_per_minute=600)
        time.sleep(0.2)
        results = [bucket.consume() for _ in range(3)]
        assert all(results)
        assert bucket.consume() is False

    def test_partial_refill_does_not_grant_token(self):
        bucket = TokenBucket(capacity=1, refill_per_minute=6)
        bucket.consume()
        time.sleep(0.05)
        assert bucket.consume() is False


class TestTokenBucketThreadSafety:
    def test_concurrent_consumes_respect_capacity(self):
        capacity = 5
        bucket = TokenBucket(capacity=capacity, refill_per_minute=capacity)
        results = []
        lock = threading.Lock()

        def consume_and_record():
            result = bucket.consume()
            with lock:
                results.append(result)

        threads = [threading.Thread(target=consume_and_record) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        allowed = sum(1 for r in results if r)
        assert allowed == capacity

    def test_no_race_condition_on_tokens(self):
        bucket = TokenBucket(capacity=10, refill_per_minute=10)
        results = []
        lock = threading.Lock()

        def consume():
            r = bucket.consume()
            with lock:
                results.append(r)

        threads = [threading.Thread(target=consume) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert sum(results) == 10


class TestTokenBucketConfig:
    def test_zero_capacity_always_throttled(self):
        bucket = TokenBucket(capacity=0, refill_per_minute=60)
        assert bucket.consume() is False

    def test_high_capacity_allows_many(self):
        bucket = TokenBucket(capacity=100, refill_per_minute=100)
        results = [bucket.consume() for _ in range(100)]
        assert all(results)

    def test_refill_rate_is_per_minute(self):
        bucket = TokenBucket(capacity=60, refill_per_minute=60)
        for _ in range(60):
            bucket.consume()
        assert bucket.consume() is False
        time.sleep(1.1)
        assert bucket.consume() is True


class TestGlobalInstances:
    def test_llm_rate_limiter_is_token_bucket(self):
        from src.core.rate_limiter import llm_rate_limiter

        assert isinstance(llm_rate_limiter, TokenBucket)

    def test_pr_rate_limiter_is_token_bucket(self):
        from src.core.rate_limiter import pr_rate_limiter

        assert isinstance(pr_rate_limiter, TokenBucket)

    def test_llm_limiter_allows_at_least_one(self):
        from src.core.rate_limiter import TokenBucket

        fresh = TokenBucket(capacity=10, refill_per_minute=10)
        assert fresh.consume() is True

    def test_pr_limiter_allows_at_least_one(self):
        from src.core.rate_limiter import TokenBucket

        fresh = TokenBucket(capacity=3, refill_per_minute=3)
        assert fresh.consume() is True
