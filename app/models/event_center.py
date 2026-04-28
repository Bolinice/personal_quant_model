"""事件中心模型"""

from sqlalchemy import BigInteger, Column, Date, DateTime, Numeric, String, Text
from sqlalchemy.sql import func

from app.db.base import Base


class EventCenter(Base):
    """事件中心表 - 业绩预告/问询函/立案处罚/减持/股权质押等"""

    __tablename__ = "event_center"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    stock_id = Column(BigInteger, nullable=False, index=True, comment="股票ID")
    event_type = Column(
        String(50),
        nullable=False,
        index=True,
        comment="事件类型: earnings_preview/regulatory/corporate/pledge/reduction/repurchase/unlock",
    )
    event_subtype = Column(String(100), comment="事件子类型")
    event_date = Column(Date, nullable=False, index=True, comment="事件日期")
    effective_date = Column(Date, comment="生效日期")
    expire_date = Column(Date, comment="失效日期")
    severity = Column(String(20), comment="严重程度: info/warning/critical")
    score = Column(Numeric(10, 4), comment="事件分数(0~1)")
    title = Column(Text, comment="事件标题")
    content = Column(Text, comment="事件内容")
    source = Column(String(100), comment="来源")
    snapshot_id = Column(String(50), index=True, comment="快照ID")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

    __table_args__ = ({"comment": "事件中心表"},)
