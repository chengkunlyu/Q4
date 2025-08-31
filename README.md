# Q4 – API Rate Limiting & Retry Mechanism

This repository contains a Python implementation for dynamic API rate limiting,
fault-tolerant retry logic, and graceful degradation to support rate limit changes.

## Components

- `decorators.py`: Core implementation including
  - DynamicRateLimiter (token bucket with adjustable rate)
  - CircuitBreaker (failsafe for sustained errors)
  - `resilient` decorator (with exponential backoff and dead-letter queue)

## Demo

The decorated function simulates an API that returns:
- normal success (status 200)
- every 20th call returns status 429 with a new rate limit (`X-Rate-Limit-RPS: 10`)

### Run the demonstration:

```bash
python Q4.py

## Output
success:60 dead_letter:0
