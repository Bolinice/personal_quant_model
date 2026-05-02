"""
P0 关键问题修复脚本
修复影响正确性和安全性的严重问题
"""

# ============================================================
# 修复1: T+1约束的日终重置逻辑
# ============================================================

# 文件: app/core/backtest_engine.py
# 在 ABShareBacktestEngine 类中添加方法

def on_market_open(self, state: BacktestState):
    """
    每日开盘前重置T+1标记

    修复问题: 当前实现中 shares_bought_today 从不重置，
    导致第2天及以后所有历史买入的股票都无法卖出
    """
    for pos in state.positions.values():
        pos.shares_bought_today = 0

    logger.debug(f"[{state.current_date}] 重置T+1标记，当前持仓数: {len(state.positions)}")


# 在 run() 方法的日期循环中调用
def run(self, ...):
    for date in trading_dates:
        state.current_date = date

        # ✅ 添加：每日开盘前重置T+1标记
        self.on_market_open(state)

        # 原有逻辑...
        self.rebalance(state, signals_today, prices_today)
        self.calc_nav(state, prices_today)


# ============================================================
# 修复2: 标签构建的未来函数风险
# ============================================================

# 文件: app/core/labels.py
# 在 LabelGenerator.generate_excess_return_labels() 方法开头添加

def generate_excess_return_labels(
    self,
    df: pd.DataFrame,
    forward_periods: list[int] = None,
    benchmark_df: pd.DataFrame = None,
    exclude_codes: list[str] = None,
    industry_col: str = None,
) -> pd.DataFrame:
    """生成超额收益标签"""

    # ✅ 添加：强制要求提供基准或排除列表
    if benchmark_df is None and not exclude_codes:
        raise ValueError(
            "Must provide either benchmark_df or exclude_codes to avoid look-ahead bias. "
            "When using market average as benchmark, the evaluated stock itself must be excluded."
        )

    # 原有逻辑...


# ============================================================
# 修复3: 支付API添加认证
# ============================================================

# 文件: app/api/v1/payments.py
# 修改所有支付相关端点

from app.api.deps import get_current_user
from app.models.users import User

@router.post("/orders", response_model=PaymentOrderResponse)
def create_order(
    order_data: PaymentOrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)  # ✅ 添加认证
):
    """创建支付订单（需要认证）"""

    # ✅ 添加：验证用户权限
    if order_data.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="无权为其他用户创建订单"
        )

    # 原有逻辑...


@router.get("/orders/{order_no}", response_model=PaymentOrderResponse)
def get_order(
    order_no: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)  # ✅ 添加认证
):
    """查询订单详情（需要认证）"""

    order = db.query(PaymentOrder).filter(PaymentOrder.order_no == order_no).first()
    if not order:
        raise HTTPException(404, "订单不存在")

    # ✅ 添加：验证用户权限
    if order.user_id != current_user.id:
        raise HTTPException(403, "无权查看其他用户的订单")

    return order


@router.post("/orders/{order_no}/refund")
def refund_order(
    order_no: str,
    refund_data: RefundRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)  # ✅ 添加认证
):
    """申请退款（需要认证）"""

    order = db.query(PaymentOrder).filter(PaymentOrder.order_no == order_no).first()
    if not order:
        raise HTTPException(404, "订单不存在")

    # ✅ 添加：验证用户权限
    if order.user_id != current_user.id:
        raise HTTPException(403, "无权操作其他用户的订单")

    # 原有逻辑...


# ============================================================
# 修复4: JWT黑名单迁移到Redis
# ============================================================

# 文件: app/services/auth_service.py
# 替换内存存储为Redis

import hashlib
from app.core.cache import cache_service

class AuthService:
    # ❌ 删除内存存储
    # _revoked_tokens: set[str] = set()

    @staticmethod
    def revoke_token(refresh_token: str) -> None:
        """撤销刷新令牌（使用Redis存储）"""
        # ✅ 使用Redis存储
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        cache_service.set(
            f"revoked_token:{token_hash}",
            "1",
            ttl=7 * 86400  # 7天过期
        )
        logger.info(f"Token revoked: {token_hash[:16]}...")

    @staticmethod
    def is_token_revoked(refresh_token: str) -> bool:
        """检查令牌是否已撤销"""
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        return cache_service.get(f"revoked_token:{token_hash}") is not None


# ============================================================
# 修复5: 支付回调改用logger
# ============================================================

# 文件: app/api/v1/payments.py
# 替换所有 print() 为 logger

from app.core.logging import logger
from fastapi.responses import Response

@router.post("/callback/alipay")
async def alipay_callback(request: Request, db: Session = Depends(get_db)):
    """支付宝支付回调"""
    try:
        form_data = await request.form()
        data = dict(form_data)

        # ✅ 使用logger替代print
        logger.info("收到支付宝回调", extra={
            "out_trade_no": data.get("out_trade_no"),
            "trade_no": data.get("trade_no"),
            "trade_status": data.get("trade_status")
        })

        # 验证签名
        alipay_service = AlipayAdapter(...)
        if not alipay_service.verify_callback(data):
            logger.warning("支付宝回调签名验证失败", extra={"data": data})
            return Response(content="fail", media_type="text/plain")

        # 处理订单状态
        # ...

        logger.info("支付宝回调处理成功", extra={"order_no": order.order_no})
        return Response(content="success", media_type="text/plain")

    except Exception as e:
        # ✅ 使用logger记录错误
        logger.error("支付宝回调处理失败", exc_info=True, extra={
            "error": str(e),
            "data": data if 'data' in locals() else None
        })
        return Response(content="fail", media_type="text/plain")


# ============================================================
# 修复6: 前端测试基础设施
# ============================================================

# 文件: frontend/src/test/setup.ts
# 添加缺失的全局mock

import { vi } from 'vitest';

// ✅ 添加localStorage mock
global.localStorage = {
  getItem: vi.fn((key: string) => null),
  setItem: vi.fn((key: string, value: string) => {}),
  removeItem: vi.fn((key: string) => {}),
  clear: vi.fn(() => {}),
  length: 0,
  key: vi.fn((index: number) => null),
};

// ✅ 添加sessionStorage mock
global.sessionStorage = {
  getItem: vi.fn((key: string) => null),
  setItem: vi.fn((key: string, value: string) => {}),
  removeItem: vi.fn((key: string) => {}),
  clear: vi.fn(() => {}),
  length: 0,
  key: vi.fn((index: number) => null),
};

// ✅ 添加document mock
Object.defineProperty(global, 'document', {
  value: {
    createElement: vi.fn(() => ({})),
    getElementById: vi.fn(() => null),
    querySelector: vi.fn(() => null),
    querySelectorAll: vi.fn(() => []),
  },
  writable: true,
});

// ✅ 添加window.matchMedia mock
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation(query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});


# ============================================================
# 修复7: 前端useQuery重构
# ============================================================

# 文件: frontend/src/hooks/useQuery.ts
# 避免在effect中同步调用setState

import { useCallback, useEffect, useRef, useState, useTransition } from 'react';

export function useQuery<T>(
  queryFn: () => Promise<T>,
  deps: any[] = []
) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [isPending, startTransition] = useTransition();

  // ✅ 使用useCallback稳定引用
  const execute = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const result = await queryFn();
      // ✅ 使用startTransition包装setState
      startTransition(() => {
        setData(result);
        setLoading(false);
      });
    } catch (err) {
      startTransition(() => {
        setError(err as Error);
        setLoading(false);
      });
    }
  }, [queryFn]);

  // ✅ 移除execute依赖，避免循环
  useEffect(() => {
    execute();
  }, deps);

  return { data, loading: loading || isPending, error, refetch: execute };
}


# ============================================================
# 修复8: 数据库N+1查询
# ============================================================

# 文件: app/services/factors_service.py
# 批量查询替代逐条查询

def calculate_factor_ic_decay(factor_name: str, db: Session) -> dict:
    """计算因子IC衰减（优化版）"""

    # 获取因子值
    df = pd.read_sql(
        db.query(FactorValue)
        .filter(FactorValue.factor_name == factor_name)
        .statement,
        db.bind
    )

    if df.empty:
        return {}

    # ✅ 批量查询所有需要的收益率数据
    security_ids = df['security_id'].unique().tolist()
    next_dates = df['trade_date'].apply(get_next_trading_date).unique().tolist()

    returns_data = db.query(
        StockDaily.ts_code,
        StockDaily.trade_date,
        StockDaily.pct_chg
    ).filter(
        StockDaily.ts_code.in_(security_ids),
        StockDaily.trade_date.in_(next_dates)
    ).all()

    # ✅ 构建字典用于快速查找
    returns_dict = {
        (r.ts_code, r.trade_date): float(r.pct_chg) if r.pct_chg else 0
        for r in returns_data
    }

    # ✅ 向量化计算
    df['next_return'] = df.apply(
        lambda row: returns_dict.get(
            (row['security_id'], get_next_trading_date(row['trade_date'])),
            0
        ),
        axis=1
    )

    # 计算IC
    ic = df.groupby('trade_date').apply(
        lambda g: g['factor_value'].corr(g['next_return'])
    )

    return {
        'mean_ic': ic.mean(),
        'std_ic': ic.std(),
        'ic_ir': ic.mean() / ic.std() if ic.std() > 0 else 0,
    }


print("""
P0关键问题修复清单：

✅ 1. T+1约束日终重置 (backtest_engine.py)
✅ 2. 标签构建未来函数检查 (labels.py)
✅ 3. 支付API添加认证 (payments.py)
✅ 4. JWT黑名单迁移Redis (auth_service.py)
✅ 5. 支付回调使用logger (payments.py)
✅ 6. 前端测试基础设施 (setup.ts)
✅ 7. useQuery重构 (useQuery.ts)
✅ 8. N+1查询优化 (factors_service.py)

请按照上述代码修改相应文件。
""")
