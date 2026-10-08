# Redis caching

Redis is an optional shared cache for observation retrieval and classification. SQLite/PostgreSQL remain the durable source of truth. Current coverage: observation pages, theme/severity/recurrence metrics, related-observation responses and versioned classification tags. The agent benefits because it uses these same services. Existing portfolio risk calculations are unchanged; portfolio dashboard queries are not newly cached by this layer.

Request flow: determine the latest completed database run → build a scoped Redis key → validate cached data → return a hit, or query the database and populate Redis. Keys include application namespace, cache schema version, database path, completed run ID, every filter, grouping and pagination argument. New runs automatically use a different namespace of keys; old entries expire. Running/incomplete runs are not cached. The latest run is always resolved from the database, so Redis cannot freeze the app on an old snapshot.

Classification flow: Redis lookup → strict Pydantic/evidence/provenance validation → durable SQLite cache insert → normal assignment/evidence workflow. On a miss, reuse SQLite classification cache or classify normally. Valid classifications populate Redis with a separate TTL. Fallbacks are never cached as successful AI results. `AI_CACHE_ENABLED=false` bypasses classification caches; `REDIS_ENABLED=false` disables the Redis layer entirely.

Only JSON is stored; no pickle or executable serialization. API keys and Redis URLs are not in cached values or status responses. Redis can contain original observation evidence, so use a private instance appropriate for the source data. The Docker service is internal-only; the separate local development compose file publishes port 6379 only on loopback.

## Local Python with Docker Redis

```powershell
docker compose -f docker-compose.redis.yml up -d
$env:REDIS_ENABLED='true'
$env:REDIS_URL='redis://127.0.0.1:6379/0'
.venv\Scripts\python.exe -m pip install -r requirements.txt
.\start-real.ps1
```

Alternatively, `docker compose up --build -d` starts PostgreSQL, Redis and the app together. Docker bootstrap retains its existing synthetic-data behavior; it does not import the desktop workbooks automatically. The intelligence database has its own durable Docker volume. Generate the intelligence snapshot inside the app container with `docker compose exec app python -m data_engineering.tag_observations --provider rules` when needed. Redis is disposable and does not need a volume because authoritative classifications remain in SQLite.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| REDIS_ENABLED | false; true in full Compose | Enable cache access |
| REDIS_URL | redis://127.0.0.1:6379/0 | Private connection; supports redis-py URL credentials/TLS configuration |
| REDIS_NAMESPACE | inspection-insights | Separate applications/environments |
| REDIS_CACHE_TTL_SECONDS | 300 | Retrieval entry lifetime |
| REDIS_CLASSIFICATION_TTL_SECONDS | 86400 | Validated tag lifetime |
| REDIS_TIMEOUT_SECONDS | 0.25 | Connect/read timeout |
| REDIS_MAX_VALUE_BYTES | 2000000 | Skip oversized responses |

The Docker Redis instance has a 128 MB memory limit and `allkeys-lru` eviction policy, with Redis disk snapshots/AOF disabled. Bounded connection pools and no automatic Redis retries limit outage latency. A failure opens a 30-second local circuit breaker; requests use the database during that interval, then retry Redis. Eviction, restart or expiration loses only acceleration, not evidence. Cold requests still pay the original SQL cost. Concurrent cold requests can still duplicate SQL work; distributed request coalescing is not implemented.

GET `/api/cache/status` reports enabled/connected/unavailable/disabled, TTL and per-worker hits, misses, writes, errors, invalid entries and oversized values. It never returns the connection string. Counters reset when the process restarts, and hits count retrieved JSON before subsequent typed validation. Database fallback does not make an unavailable Redis server look healthy.

## Validation

`python -m pip install -r requirements-test.txt` installs the Redis emulator used only in tests. `python -m pytest tests/test_redis_cache.py -q` covers cache hits avoiding expensive queries, pagination/filter/run isolation, cached-result independence, aggregates/similarity, corrupt JSON, wrong run IDs, invented evidence, unavailable Redis, circuit recovery, disabled mode, TTL, size bounds and restoration of durable classifications. These are emulator integration tests, not evidence of a production Redis deployment.

The implementation follows the official [redis-py client documentation](https://redis.io/docs/latest/develop/clients/redis-py/) and [Redis eviction guidance](https://redis.io/docs/latest/develop/reference/eviction/). No cloud Redis account or paid service was created.
