"""
自定義異常類
統一錯誤處理策略
"""


class ConfigError(Exception):
    """配置相關錯誤基類"""
    def __init__(self, message: str, config_path: str = None, details: dict = None):
        super().__init__(message)
        self.config_path = config_path
        self.details = details or {}
    
    def __str__(self):
        base_msg = super().__str__()
        if self.config_path:
            base_msg = f"{base_msg} (配置文件: {self.config_path})"
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            base_msg = f"{base_msg} [詳細信息: {details_str}]"
        return base_msg


class ConfigValidationError(ConfigError):
    """配置驗證錯誤"""
    def __init__(self, message: str, field: str = None, value=None, **kwargs):
        super().__init__(message, **kwargs)
        self.field = field
        self.value = value


class ConfigLoadError(ConfigError):
    """配置加載錯誤"""
    pass


class ConfigSaveError(ConfigError):
    """配置保存錯誤"""
    pass


class ConfigBackupError(ConfigError):
    """配置備份錯誤"""
    pass


class ConfigRestoreError(ConfigError):
    """配置恢復錯誤"""
    pass


class EnvironmentVariableError(ConfigError):
    """環境變量錯誤"""
    def __init__(self, message: str, var_name: str = None, **kwargs):
        super().__init__(message, **kwargs)
        self.var_name = var_name


class DaemonError(Exception):
    """守護進程相關錯誤基類"""
    pass


class DaemonStartError(DaemonError):
    """守護進程啟動錯誤"""
    pass


class DaemonStopError(DaemonError):
    """守護進程停止錯誤"""
    pass


class DaemonConfigError(DaemonError):
    """守護進程配置錯誤"""
    pass