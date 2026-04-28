from prometheus_client import Counter, Gauge, Histogram

# 创建指标
REQUEST_COUNT = Counter("http_requests_total", "Total HTTP requests", ["method", "endpoint", "status_code"])

REQUEST_DURATION = Histogram("http_request_duration_seconds", "HTTP request duration")

ACTIVE_USERS = Gauge("active_users_total", "Number of active users")

TASK_QUEUE_SIZE = Gauge("task_queue_size", "Number of tasks in queue")

DATABASE_CONNECTIONS = Gauge("database_connections", "Number of active database connections")

RATE_LIMIT_EXCEEDED = Counter("rate_limit_exceeded_total", "Rate limit exceeded", ["endpoint"])


def record_request(method: str, endpoint: str, status_code: int, duration: float):
    """记录HTTP请求指标"""
    REQUEST_COUNT.labels(method=method, endpoint=endpoint, status_code=status_code).inc()
    REQUEST_DURATION.observe(duration)


def increment_active_users():
    """增加活跃用户数"""
    ACTIVE_USERS.inc()


def decrement_active_users():
    """减少活跃用户数"""
    ACTIVE_USERS.dec()


def update_task_queue_size(size: int):
    """更新任务队列大小"""
    TASK_QUEUE_SIZE.set(size)


def update_database_connections(count: int):
    """更新数据库连接数"""
    DATABASE_CONNECTIONS.set(count)
