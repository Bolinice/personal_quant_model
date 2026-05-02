"""
安全头中间件

提供多层安全防护：
- CORS（跨域资源共享）
- CSP（内容安全策略）
- HSTS（HTTP 严格传输安全）
- X-Frame-Options（防止点击劫持）
- X-Content-Type-Options（防止 MIME 类型嗅探）
- X-XSS-Protection（XSS 防护）
- Referrer-Policy（引用策略）
"""

from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """安全头中间件"""

    def __init__(
        self,
        app: ASGIApp,
        *,
        enable_hsts: bool = True,
        hsts_max_age: int = 31536000,  # 1 年
        hsts_include_subdomains: bool = True,
        hsts_preload: bool = False,
        enable_csp: bool = True,
        csp_directives: dict[str, str] | None = None,
        enable_frame_options: bool = True,
        frame_options: str = "DENY",
        enable_content_type_options: bool = True,
        enable_xss_protection: bool = True,
        enable_referrer_policy: bool = True,
        referrer_policy: str = "strict-origin-when-cross-origin",
    ):
        """
        初始化安全头中间件

        Args:
            app: ASGI 应用
            enable_hsts: 是否启用 HSTS
            hsts_max_age: HSTS 最大年龄（秒）
            hsts_include_subdomains: HSTS 是否包含子域名
            hsts_preload: HSTS 是否启用预加载
            enable_csp: 是否启用 CSP
            csp_directives: CSP 指令字典
            enable_frame_options: 是否启用 X-Frame-Options
            frame_options: X-Frame-Options 值（DENY/SAMEORIGIN）
            enable_content_type_options: 是否启用 X-Content-Type-Options
            enable_xss_protection: 是否启用 X-XSS-Protection
            enable_referrer_policy: 是否启用 Referrer-Policy
            referrer_policy: Referrer-Policy 值
        """
        super().__init__(app)
        self.enable_hsts = enable_hsts
        self.hsts_max_age = hsts_max_age
        self.hsts_include_subdomains = hsts_include_subdomains
        self.hsts_preload = hsts_preload
        self.enable_csp = enable_csp
        self.csp_directives = csp_directives or {
            "default-src": "'self'",
            "script-src": "'self' 'unsafe-inline'",
            "style-src": "'self' 'unsafe-inline'",
            "img-src": "'self' data: https:",
            "font-src": "'self' data:",
            "connect-src": "'self'",
            "frame-ancestors": "'none'",
        }
        self.enable_frame_options = enable_frame_options
        self.frame_options = frame_options
        self.enable_content_type_options = enable_content_type_options
        self.enable_xss_protection = enable_xss_protection
        self.enable_referrer_policy = enable_referrer_policy
        self.referrer_policy = referrer_policy

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求并添加安全头"""
        response = await call_next(request)

        # HSTS（仅 HTTPS）
        if self.enable_hsts and request.url.scheme == "https":
            hsts_value = f"max-age={self.hsts_max_age}"
            if self.hsts_include_subdomains:
                hsts_value += "; includeSubDomains"
            if self.hsts_preload:
                hsts_value += "; preload"
            response.headers["Strict-Transport-Security"] = hsts_value

        # CSP
        if self.enable_csp:
            csp_value = "; ".join(f"{k} {v}" for k, v in self.csp_directives.items())
            response.headers["Content-Security-Policy"] = csp_value

        # X-Frame-Options
        if self.enable_frame_options:
            response.headers["X-Frame-Options"] = self.frame_options

        # X-Content-Type-Options
        if self.enable_content_type_options:
            response.headers["X-Content-Type-Options"] = "nosniff"

        # X-XSS-Protection
        if self.enable_xss_protection:
            response.headers["X-XSS-Protection"] = "1; mode=block"

        # Referrer-Policy
        if self.enable_referrer_policy:
            response.headers["Referrer-Policy"] = self.referrer_policy

        return response
