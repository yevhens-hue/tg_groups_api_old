# Deployment Guide

## Pre-deployment Checklist

### 1. Environment Variables (Render)

**Required:**
- `TG_API_ID` - Telegram API ID
- `TG_API_HASH` - Telegram API Hash
- `TG_SESSION_STRING` - Telegram session string (preferred)

**Recommended:**
- `REDIS_URL` - Redis connection URL for distributed rate limiting and shared cache
- `LOG_LEVEL` - Logging level (INFO, WARNING, ERROR)

**Optional (tuning):**
- `HTTP_RATE_LIMIT_RPM` - Rate limit per IP (default: 60)
- `CIRCUIT_BREAKER_FAILURE_THRESHOLD` - Circuit breaker threshold (default: 5)
- `TG_RPC_TIMEOUT_SEC` - RPC timeout (default: 25)
- `HTTP_TIMEOUT_SEC` - HTTP timeout (default: 30)

### 2. Generate Telegram Session

```bash
# Locally
python login.py
# Copy TG_SESSION_STRING to Render environment
```

### 3. Redis Setup (Optional but Recommended)

For production with multiple instances, set up Redis:
- Render Redis addon, or
- External Redis service
- Set `REDIS_URL` environment variable

## Deployment Steps

### Render.com

1. **Create Web Service**
   - Connect GitHub repository
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `./start.sh` or `uvicorn app:app --host 0.0.0.0 --port $PORT`

2. **Set Environment Variables**
   - Go to Environment tab
   - Add all required variables (see above)

3. **Health Check**
   - Endpoint: `/health`
   - Expected: `{"ok": true, "telegram": "ok", "redis": "ok"}`

4. **Monitor**
   - Check logs for startup messages
   - Verify `/metrics` endpoint (Prometheus)
   - Monitor `/health` endpoint

## Post-deployment Verification

### 1. Health Check
```bash
curl https://your-service.onrender.com/health
```

Expected response:
```json
{
  "ok": true,
  "telegram": "ok",
  "me_id": 123456789,
  "redis": "ok"
}
```

### 2. Test Endpoints
```bash
# Root endpoint
curl https://your-service.onrender.com/

# Search groups
curl -X POST https://your-service.onrender.com/search_groups \
  -H "Content-Type: application/json" \
  -d '{"query": "python", "limit": 5}'

# Get admins
curl -X POST https://your-service.onrender.com/get_group_admins \
  -H "Content-Type: application/json" \
  -d '{"chat_id": -1001234567890, "limit": 10}'
```

### 3. Metrics
```bash
curl https://your-service.onrender.com/metrics
```

## Monitoring

### Key Metrics (Prometheus)
- `http_requests_total` - Total HTTP requests by method, endpoint, status
- `http_request_duration_seconds` - Request latency
- `circuit_breaker_state` - Circuit breaker state (0=closed, 1=half_open, 2=open)
- `rate_limit_rejected_total` - Rate limit rejections

### Health Monitoring
- Monitor `/health` endpoint (should return `ok: true`)
- Alert on circuit breaker OPEN state
- Alert on high error rates (5xx status codes)

### Logs
- Request logging: all requests logged with timing
- Error logging: exceptions logged with request_id
- Structured logging: JSON format with request_id tracking

## Troubleshooting

### Telegram Connection Issues
- Check `TG_SESSION_STRING` is valid
- Verify `TG_API_ID` and `TG_API_HASH` are correct
- Check logs for `telegram_not_authorized` errors

### Redis Connection Issues
- Verify `REDIS_URL` is correct
- Check Redis service is accessible
- Service will fallback to in-memory cache if Redis unavailable

### Rate Limiting
- Check `X-RateLimit-*` headers in responses
- Monitor `rate_limit_rejected_total` metric
- Adjust `HTTP_RATE_LIMIT_RPM` if needed

### Circuit Breaker
- Monitor `circuit_breaker_state` metric
- If OPEN: Telegram API is down or rate limited
- Will auto-recover after `CIRCUIT_BREAKER_RECOVERY_TIMEOUT_SEC`

## Rollback

If deployment fails:
1. Revert to previous commit
2. Render will auto-deploy
3. Check logs for errors
4. Verify environment variables

## Performance Tuning

### For High Traffic (×10)
- Enable Redis for distributed rate limiting
- Increase `HTTP_RATE_LIMIT_RPM` if needed
- Monitor circuit breaker thresholds

### For Very High Traffic (×100)
- Consider connection pooling for TelegramClient (future improvement)
- Scale horizontally with Redis
- Monitor Redis connection pool size



