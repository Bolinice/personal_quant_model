# 安全中间件使用指南

本指南介绍如何使用项目中的安全头中间件和速率限制中间件来保护 FastAPI 应用。

## 目录

- [安全头中间件](#安全头中间件)
- [速率限制中间件](#速率限制中间件)
- [集成示例](#集成示例)
- [最佳实践](#最佳实践)

---

## 安全头中间件

`SecurityHeadersMiddleware` 自动为所有响应添加安全相关的 HTTP 头，防止常见的 Web 安全漏洞。

### 支持的安全头

| 安全头 | 默认值 | 说明 |
|--------|--------|------|
| **HSTS** | `max-age=31536000; includeSubDomains` | 强制使用 HTTPS |
| **CSP** | `default-src 'self'` | 内容安全策略 |
| **X-Frame-Options** | `DENY` | 防止点击劫持 |
| **X-Content-Type-Options** | `nosniff` | 防止 MIME 类型嗅探 |
| **X-XSS-Protection** | `1; mode=block` | XSS 过滤器 |
| **Referrer-Policy** | `strict-origin-when-cross-origin` | 控制 Referer 信息 |

### 基本用法

```python
from fastapi import FastAPI
from app.middleware.security import SecurityHeadersMiddleware

app = FastAPI()

# 使用默认配置
app.add_middleware(SecurityHeadersMiddleware)
```

### 自定义配置

```python
# 自定义 HSTS
app.add_middleware(
    SecurityHeadersMiddleware,
    hsts_max_age=63072000,  # 2 年
    hsts_include_subdomains=True,
    hsts_preload=True,
)

# 自定义 CSP
app.add_middleware(
    SecurityHeadersMiddleware,
    csp_directives={
        "default-src": ["'self'"],
        "script-src": ["'self'", "https://cdn.example.com"],
        "style-src": ["'self'", "'unsafe-inline'"],
        "img-src": ["'self'", "data:", "https:"],
    },
)

# 自定义 X-Frame-Options
app.add_middleware(
    SecurityHeadersMiddleware,
    frame_options="SAMEORIGIN",  # 允许同源嵌套
)
```

### CORS 配置

```python
app.add_middleware(
    SecurityHeadersMiddleware,
    cors_origins=[
        "https://example.com",
        "https://app.example.com",
    ],
    cors_allow_credentials=True,
    cors_allow_methods=["GET", "POST", "PUT", "DELETE"],
    cors_allow_headers=["Authorization", "Content-Type"],
    cors_max_age=3600,
)
```

### 禁用特定安全头

```python
app.add_middleware(
    SecurityHeadersMiddleware,
    hsts_max_age=0,  # 禁用 HSTS
    csp_directives=None,  # 禁用 CSP
)
```

---

## 速率限制中间件

`RateLimitMiddleware` 使用滑动窗口算法限制客户端请求频率，防止 API 滥用和 DDoS 攻击。

### 基本用法

```python
from fastapi import FastAPI
from app.middleware.rate_limit import RateLimitMiddleware, InMemoryRateLimiter

app = FastAPI()

# 使用内存后端（适合单机部署）
limiter = InMemoryRateLimiter()
app.add_middleware(
    RateLimitMiddleware,
    limiter=limiter,
    default_limit=100,  # 每分钟 100 次请求
    default_window=60,  # 60 秒窗口
)
```

### Redis 后端（推荐生产环境）

```python
from app.middleware.rate_limit import RedisRateLimiter
import redis.asyncio as redis

# 创建 Redis 连接
redis_client = redis.from_url("redis://localhost:6379")

# 使用 Redis 后端（适合分布式部署）
limiter = RedisRateLimiter(redis_client)
app.add_middleware(
    RateLimitMiddleware,
    limiter=limiter,
    default_limit=100,
    default_window=60,
)
```

### 自定义限流键

默认情况下，速率限制基于客户端 IP 地址。你可以自定义限流键：

```python
from fastapi import Request

def custom_key_func(request: Request) -> str:
    """基于用户 ID 限流"""
    user_id = request.state.user_id if hasattr(request.state, "user_id") else None
    if user_id:
        return f"user:{user_id}"
    # 回退到 IP 地址
    return request.client.host if request.client else "unknown"

app.add_middleware(
    RateLimitMiddleware,
    limiter=limiter,
    key_func=custom_key_func,
)
```

### 豁免特定路径

```python
app.add_middleware(
    RateLimitMiddleware,
    limiter=limiter,
    exempt_paths=[
        "/health",
        "/metrics",
        "/docs",
        "/openapi.json",
    ],
)
```

### 响应头

当请求被限流时，中间件会返回以下响应头：

```http
HTTP/1.1 429 Too Many Requests
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1234567890
Retry-After: 42
```

- `X-RateLimit-Limit`: 时间窗口内允许的最大请求数
- `X-RateLimit-Remaining`: 剩余可用请求数
- `X-RateLimit-Reset`: 限流重置时间（Unix 时间戳）
- `Retry-After`: 建议重试等待时间（秒）

---

## 集成示例

### 完整配置示例

```python
from fastapi import FastAPI, Request
from app.middleware.security import SecurityHeadersMiddleware
from app.middleware.rate_limit import RateLimitMiddleware, InMemoryRateLimiter

app = FastAPI()

# 1. 安全头中间件
app.add_middleware(
    SecurityHeadersMiddleware,
    # HSTS 配置
    hsts_max_age=31536000,
    hsts_include_subdomains=True,
    # CSP 配置
    csp_directives={
        "default-src": ["'self'"],
        "script-src": ["'self'", "https://cdn.jsdelivr.net"],
        "style-src": ["'self'", "'unsafe-inline'"],
        "img-src": ["'self'", "data:", "https:"],
        "font-src": ["'self'", "https://fonts.gstatic.com"],
        "connect-src": ["'self'", "https://api.example.com"],
    },
    # CORS 配置
    cors_origins=[
        "https://example.com",
        "https://app.example.com",
    ],
    cors_allow_credentials=True,
)

# 2. 速率限制中间件
def get_rate_limit_key(request: Request) -> str:
    """优先使用用户 ID，回退到 IP"""
    if hasattr(request.state, "user") and request.state.user:
        return f"user:{request.state.user.id}"
    return request.client.host if request.client else "unknown"

limiter = InMemoryRateLimiter()
app.add_middleware(
    RateLimitMiddleware,
    limiter=limiter,
    default_limit=100,
    default_window=60,
    key_func=get_rate_limit_key,
    exempt_paths=["/health", "/metrics"],
)

@app.get("/")
async def root():
    return {"message": "Hello World"}
```

### 与认证中间件配合

```python
from fastapi import FastAPI, Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 从 JWT 提取用户信息
        token = request.headers.get("Authorization")
        if token:
            user = await verify_token(token)
            request.state.user = user
        
        response = await call_next(request)
        return response

app = FastAPI()

# 中间件顺序很重要！
# 1. 先认证（提取用户信息）
app.add_middleware(AuthMiddleware)

# 2. 再限流（使用用户信息）
app.add_middleware(
    RateLimitMiddleware,
    limiter=limiter,
    key_func=lambda req: f"user:{req.state.user.id}" if hasattr(req.state, "user") else req.client.host,
)

# 3. 最后添加安全头
app.add_middleware(SecurityHeadersMiddleware)
```

---

## 最佳实践

### 1. 安全头配置

**生产环境推荐配置**：

```python
app.add_middleware(
    SecurityHeadersMiddleware,
    # 启用严格的 HSTS
    hsts_max_age=63072000,  # 2 年
    hsts_include_subdomains=True,
    hsts_preload=True,
    
    # 严格的 CSP
    csp_directives={
        "default-src": ["'self'"],
        "script-src": ["'self'"],
        "style-src": ["'self'"],
        "img-src": ["'self'", "data:"],
        "font-src": ["'self'"],
        "connect-src": ["'self'"],
        "frame-ancestors": ["'none'"],
        "base-uri": ["'self'"],
        "form-action": ["'self'"],
    },
    
    # 防止点击劫持
    frame_options="DENY",
    
    # 明确的 CORS 白名单
    cors_origins=["https://yourdomain.com"],
)
```

**开发环境配置**：

```python
app.add_middleware(
    SecurityHeadersMiddleware,
    # 宽松的 CSP（允许 unsafe-inline 用于热重载）
    csp_directives={
        "default-src": ["'self'", "'unsafe-inline'", "'unsafe-eval'"],
    },
    
    # 允许所有来源（仅开发环境！）
    cors_origins=["*"],
)
```

### 2. 速率限制策略

**分层限流**：

```python
# 全局限流：防止暴力攻击
app.add_middleware(
    RateLimitMiddleware,
    limiter=limiter,
    default_limit=1000,  # 每分钟 1000 次
    default_window=60,
)

# 路由级限流：保护敏感端点
from fastapi import APIRouter, Depends
from app.middleware.rate_limit import rate_limit

router = APIRouter()

@router.post("/login")
@rate_limit(limit=5, window=60)  # 每分钟 5 次登录尝试
async def login(credentials: LoginRequest):
    ...

@router.post("/api/expensive-operation")
@rate_limit(limit=10, window=3600)  # 每小时 10 次
async def expensive_operation():
    ...
```

**动态限流**：

```python
def dynamic_key_func(request: Request) -> str:
    """根据用户等级动态调整限流"""
    if hasattr(request.state, "user"):
        user = request.state.user
        tier = user.subscription_tier
        return f"user:{user.id}:tier:{tier}"
    return request.client.host

# 在业务逻辑中根据 tier 调整限制
@app.get("/api/data")
async def get_data(request: Request):
    user = request.state.user
    if user.subscription_tier == "premium":
        limit = 1000
    elif user.subscription_tier == "standard":
        limit = 100
    else:
        limit = 10
    
    # 检查限流
    key = f"user:{user.id}"
    allowed, retry_after = limiter.is_allowed(key, limit, 60)
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    return {"data": "..."}
```

### 3. 监控和告警

```python
from app.middleware.rate_limit import RateLimitMiddleware
import structlog

logger = structlog.get_logger()

class MonitoredRateLimitMiddleware(RateLimitMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            response = await super().dispatch(request, call_next)
            
            # 记录限流事件
            if response.status_code == 429:
                logger.warning(
                    "rate_limit_exceeded",
                    path=request.url.path,
                    client=request.client.host,
                    user_agent=request.headers.get("user-agent"),
                )
            
            return response
        except Exception as e:
            logger.error("rate_limit_error", error=str(e))
            raise

app.add_middleware(MonitoredRateLimitMiddleware, limiter=limiter)
```

### 4. 测试

```python
from fastapi.testclient import TestClient

def test_rate_limit():
    client = TestClient(app)
    
    # 发送 100 次请求（限制内）
    for i in range(100):
        response = client.get("/api/data")
        assert response.status_code == 200
    
    # 第 101 次请求应该被限流
    response = client.get("/api/data")
    assert response.status_code == 429
    assert "Retry-After" in response.headers

def test_security_headers():
    client = TestClient(app)
    response = client.get("/")
    
    # 验证安全头
    assert "Strict-Transport-Security" in response.headers
    assert "Content-Security-Policy" in response.headers
    assert "X-Frame-Options" in response.headers
    assert response.headers["X-Frame-Options"] == "DENY"
```

---

## 常见问题

### Q: 如何在 Kubernetes 中使用速率限制？

A: 在 Kubernetes 中，建议使用 Redis 后端以支持多副本：

```python
import redis.asyncio as redis
from app.core.config import settings

redis_client = redis.from_url(settings.REDIS_URL)
limiter = RedisRateLimiter(redis_client)
```

### Q: 如何处理反向代理后的真实 IP？

A: 使用 `X-Forwarded-For` 或 `X-Real-IP` 头：

```python
def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

app.add_middleware(
    RateLimitMiddleware,
    limiter=limiter,
    key_func=get_client_ip,
)
```

### Q: CSP 阻止了我的内联脚本怎么办？

A: 使用 nonce 或 hash：

```python
import secrets
from fastapi import Request

@app.middleware("http")
async def add_csp_nonce(request: Request, call_next):
    nonce = secrets.token_urlsafe(16)
    request.state.csp_nonce = nonce
    
    response = await call_next(request)
    
    # 在 CSP 中添加 nonce
    csp = response.headers.get("Content-Security-Policy", "")
    csp = csp.replace("script-src", f"script-src 'nonce-{nonce}'")
    response.headers["Content-Security-Policy"] = csp
    
    return response
```

### Q: 如何临时禁用某个 IP 的访问？

A: 使用黑名单：

```python
BLOCKED_IPS = {"192.168.1.100", "10.0.0.50"}

@app.middleware("http")
async def block_ips(request: Request, call_next):
    client_ip = request.client.host
    if client_ip in BLOCKED_IPS:
        return JSONResponse(
            status_code=403,
            content={"detail": "Access denied"},
        )
    return await call_next(request)
```

---

## 参考资源

- [OWASP Secure Headers Project](https://owasp.org/www-project-secure-headers/)
- [MDN Web Security](https://developer.mozilla.org/en-US/docs/Web/Security)
- [Content Security Policy Reference](https://content-security-policy.com/)
- [Rate Limiting Strategies](https://cloud.google.com/architecture/rate-limiting-strategies-techniques)
