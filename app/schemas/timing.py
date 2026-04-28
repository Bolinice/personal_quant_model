from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TimingModelBase(BaseModel):
    name: str
    description: str | None = None
    signal_type: str
    is_active: bool = True


class TimingModelCreate(TimingModelBase):
    pass


class TimingModelUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    signal_type: str | None = None
    is_active: bool | None = None


class TimingModelInDB(TimingModelBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TimingModelOut(TimingModelBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TimingModel(TimingModelOut):
    pass


class TimingSignalBase(BaseModel):
    model_id: int
    trade_date: datetime
    signal_type: str  # long, short, neutral
    exposure: float  # 仓位比例 0-1


class TimingSignalCreate(TimingSignalBase):
    pass


class TimingSignalInDB(TimingSignalBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TimingSignalOut(TimingSignalBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TimingSignal(TimingSignalOut):
    pass


class TimingConfigBase(BaseModel):
    model_id: int
    config_type: str  # ma_timing, breadth_timing, volatility_timing
    config_value: str


class TimingConfigCreate(TimingConfigBase):
    pass


class TimingConfigUpdate(BaseModel):
    config_type: str | None = None
    config_value: str | None = None


class TimingConfigInDB(TimingConfigBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TimingConfigOut(TimingConfigBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TimingConfig(TimingConfigOut):
    pass
