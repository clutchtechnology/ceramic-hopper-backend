import json
import logging
import os
from dataclasses import asdict, dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


def _default_file_path() -> str:
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', 'data', 'alarm_thresholds.json')
    )


@dataclass
class ThresholdConfig:
    warning_max: float
    alarm_max: float
    enabled: bool = True


def _tc(warning: float, alarm: float) -> ThresholdConfig:
    return ThresholdConfig(warning_max=warning, alarm_max=alarm)


@dataclass
class AlarmThresholds:
    pm10: ThresholdConfig = field(default_factory=lambda: _tc(75.0, 150.0))
    temperature: ThresholdConfig = field(default_factory=lambda: _tc(60.0, 80.0))
    voltage_a: ThresholdConfig = field(default_factory=lambda: _tc(400.0, 420.0))
    voltage_b: ThresholdConfig = field(default_factory=lambda: _tc(400.0, 420.0))
    voltage_c: ThresholdConfig = field(default_factory=lambda: _tc(400.0, 420.0))
    current_a: ThresholdConfig = field(default_factory=lambda: _tc(50.0, 80.0))
    current_b: ThresholdConfig = field(default_factory=lambda: _tc(50.0, 80.0))
    current_c: ThresholdConfig = field(default_factory=lambda: _tc(50.0, 80.0))
    power: ThresholdConfig = field(default_factory=lambda: _tc(10.0, 15.0))
    speed_x: ThresholdConfig = field(default_factory=lambda: _tc(5.0, 10.0))
    speed_y: ThresholdConfig = field(default_factory=lambda: _tc(5.0, 10.0))
    speed_z: ThresholdConfig = field(default_factory=lambda: _tc(5.0, 10.0))
    displacement_x: ThresholdConfig = field(default_factory=lambda: _tc(300.0, 500.0))
    displacement_y: ThresholdConfig = field(default_factory=lambda: _tc(300.0, 500.0))
    displacement_z: ThresholdConfig = field(default_factory=lambda: _tc(300.0, 500.0))
    freq_x: ThresholdConfig = field(default_factory=lambda: _tc(50.0, 60.0))
    freq_y: ThresholdConfig = field(default_factory=lambda: _tc(50.0, 60.0))
    freq_z: ThresholdConfig = field(default_factory=lambda: _tc(50.0, 60.0))


class AlarmThresholdManager:
    _instance: Optional['AlarmThresholdManager'] = None

    def __init__(self):
        self.thresholds = AlarmThresholds()
        self._file_path = _default_file_path()
        self._load()

    @classmethod
    def get_instance(cls) -> 'AlarmThresholdManager':
        if cls._instance is None:
            cls._instance = AlarmThresholdManager()
        return cls._instance

    def _load(self) -> None:
        if not os.path.exists(self._file_path):
            try:
                os.makedirs(os.path.dirname(self._file_path), exist_ok=True)
                with open(self._file_path, 'w', encoding='utf-8') as file:
                    json.dump(asdict(self.thresholds), file, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.warning('[AlarmThresholds] 初始化配置文件失败: path=%s, error=%s', self._file_path, e, exc_info=True)
                return
            return
        try:
            with open(self._file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
            for key, config in data.items():
                if hasattr(self.thresholds, key):
                    setattr(
                        self.thresholds,
                        key,
                        ThresholdConfig(
                            warning_max=float(config.get('warning_max', 0.0)),
                            alarm_max=float(config.get('alarm_max', 0.0)),
                            enabled=bool(config.get('enabled', True)),
                        ),
                    )
        except Exception as e:
            logger.warning('[AlarmThresholds] 加载配置文件失败: path=%s, error=%s', self._file_path, e, exc_info=True)
            return

    def save(self, data: dict) -> bool:
        updated = 0
        for key, config in data.items():
            if hasattr(self.thresholds, key):
                setattr(
                    self.thresholds,
                    key,
                    ThresholdConfig(
                        warning_max=float(config.get('warning_max', 0.0)),
                        alarm_max=float(config.get('alarm_max', 0.0)),
                        enabled=bool(config.get('enabled', True)),
                    ),
                )
                updated += 1

        try:
            os.makedirs(os.path.dirname(self._file_path), exist_ok=True)
            out = asdict(self.thresholds)
            with open(self._file_path, 'w', encoding='utf-8') as file:
                json.dump(out, file, ensure_ascii=False, indent=2)
            return updated > 0
        except Exception as e:
            logger.warning('[AlarmThresholds] 保存配置文件失败: path=%s, updated=%d, error=%s', self._file_path, updated, e, exc_info=True)
            return False

    def get_all(self) -> dict:
        return asdict(self.thresholds)

    def check_value(self, param_name: str, value: float) -> str:
        config: Optional[ThresholdConfig] = getattr(self.thresholds, param_name, None)
        if config is None or not config.enabled:
            return 'normal'
        if value > config.alarm_max:
            return 'alarm'
        if value > config.warning_max:
            return 'warning'
        return 'normal'
