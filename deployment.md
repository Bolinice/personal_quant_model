# 部署指南

## 开发环境部署

### 使用Docker Compose

1. **安装Docker和Docker Compose**
```bash
# macOS
brew install docker

# Linux
curl -sSL https://get.docker.com/ | sh
sudo curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

2. **克隆项目**
```bash
git clone <repository-url>
cd quant-platform
```

3. **配置环境变量**
```bash
cp app/.env.example app/.env
# 编辑 .env 文件设置你的配置
```

4. **启动服务**
```bash
docker-compose up -d
```

5. **查看日志**
```bash
docker-compose logs -f
```

### 本地开发

1. **创建虚拟环境**
```bash
python -m venv venv
source venv/bin/activate
```

2. **安装依赖**
```bash
pip install -r app/requirements.txt
```

3. **启动Redis**
```bash
redis-server
```

4. **启动PostgreSQL**
```bash
docker run -d --name postgres -e POSTGRES_PASSWORD=password -p 5432:5432 postgres:15
```

5. **启动Celery Worker**
```bash
celery -A app.core.celery_config worker --loglevel=info
```

6. **启动应用**
```bash
cd app
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## 生产环境部署

### 1. 准备服务器

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装Docker
curl -sSL https://get.docker.com/ | sh
sudo usermod -aG docker $USER

# 安装Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### 2. 部署应用

```bash
# 创建部署目录
sudo mkdir -p /opt/quant-platform
sudo chown -R $USER:$USER /opt/quant-platform

# 克隆项目
cd /opt/quant-platform
git clone <repository-url> .

# 配置环境变量
cp app/.env.example app/.env
# 编辑敏感信息

# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d
```

### 3. 配置反向代理

```bash
# 安装Nginx
sudo apt install nginx -y

# 创建配置文件
sudo nano /etc/nginx/sites-available/quant-platform
```

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
# 启用配置
sudo ln -s /etc/nginx/sites-available/quant-platform /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 4. 配置SSL证书

```bash
# 安装Certbot
sudo apt install certbot python3-certbot-nginx -y

# 获取证书
sudo certbot --nginx -d your-domain.com
```

### 5. 设置开机自启

```bash
# 创建服务文件
sudo nano /etc/systemd/system/quant-platform.service
```

```ini
[Unit]
Description=Quant Platform API
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/quant-platform
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down
TimeoutStartSec=0
User=root

[Install]
WantedBy=multi-user.target
```

```bash
# 启用服务
sudo systemctl daemon-reload
sudo systemctl enable quant-platform
sudo systemctl start quant-platform
```

## 监控和维护

### 1. 日志管理

```bash
# 查看服务日志
docker-compose logs -f app
docker-compose logs -f celery

# 清理日志
docker-compose logs --tail=100 app > app.log
```

### 2. 资源监控

```bash
# 查看容器资源使用
docker stats

# 查看容器详情
docker inspect quant-platform-app-1

# 监控系统资源
htop
df -h
free -h
```

### 3. 备份

```bash
# 数据库备份
docker exec quant-platform-db pg_dump -U postgres quant_platform > backup.sql

# 备份Redis
docker exec quant-platform-redis redis-cli BGSAVE
docker cp quant-platform-redis:/data/dump.rdb backup/
```

### 4. 更新

```bash
# 拉取最新代码
git pull origin main

# 重新构建镜像
docker-compose build

# 更新服务
docker-compose up -d
```

### 5. 故障排除

```bash
# 查看服务状态
docker-compose ps

# 查看错误日志
docker-compose logs app

# 重启服务
docker-compose restart app

# 重新创建服务
docker-compose up -d --force-recreate
```

## 性能优化

### 1. 数据库优化

- 配置连接池
- 添加索引
- 定期清理过期数据
- 使用读写分离

### 2. Redis缓存

- 配置LRU淘汰策略
- 设置合理的内存限制
- 使用Pipeline批量操作

### 3. Celery优化

- 配置worker并发数
- 设置任务超时
- 监控任务队列
- 实现任务重试机制

### 4. 应用优化

- 启用Gzip压缩
- 配置静态文件缓存
- 使用CDN加速
- 实现API限流