# Quick Deploy Guide

## ✅ Pre-flight Checklist

- [x] All tests passing (5/5)
- [x] All imports working
- [x] All endpoints responding
- [x] Rate limit headers present
- [x] Metrics endpoint working
- [x] Health check working

## 🚀 Render.com Deployment

### 1. Environment Variables (Required)
```
TG_API_ID=your_api_id
TG_API_HASH=your_api_hash
TG_SESSION_STRING=your_session_string
```

### 2. Environment Variables (Recommended)
```
REDIS_URL=redis://... (for distributed rate limiting)
LOG_LEVEL=INFO
```

### 3. Build & Start Commands
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `./start.sh` or `uvicorn app:app --host 0.0.0.0 --port $PORT`

### 4. Health Check URL
```
https://your-service.onrender.com/health
```

## 📊 Post-Deployment Verification

```bash
# 1. Health check
curl https://your-service.onrender.com/health

# 2. Metrics
curl https://your-service.onrender.com/metrics

# 3. Test endpoint
curl -X POST https://your-service.onrender.com/search_groups \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "limit": 5}'
```

## 🔍 Monitoring

- **Metrics:** `/metrics` (Prometheus format)
- **Health:** `/health` (check every 60s)
- **Logs:** Check Render logs for request/error tracking

## ⚠️ Important Notes

1. **Redis is optional** - Service works without it (falls back to in-memory)
2. **Circuit breaker** - Auto-recovers after 60s (configurable)
3. **Rate limiting** - 60 RPM per IP by default (configurable via `HTTP_RATE_LIMIT_RPM`)
4. **Session string** - Generate locally with `python login.py`

## 🐛 Troubleshooting

- **Telegram auth fails:** Check `TG_SESSION_STRING` is valid
- **Redis connection fails:** Service will use in-memory fallback
- **High error rate:** Check circuit breaker state in `/metrics`

## 📝 Full Documentation

See `DEPLOY.md` for detailed deployment guide.



