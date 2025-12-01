"""
配置管理器 - 多配置管理系統的核心組件
提供配置文件的創建、讀取、驗證、備份等功能
"""
import os
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass
import glob

from core.logger import setup_logger
from core.exceptions import (
    ConfigError, ConfigValidationError, ConfigLoadError,
    ConfigSaveError, ConfigBackupError, ConfigRestoreError,
    EnvironmentVariableError
)

logger = setup_logger("config_manager")


@dataclass
class ConfigInfo:
    """配置信息數據類"""
    name: str
    path: str
    exchange: str
    symbol: str
    market_type: str
    strategy: str
    created_at: str
    updated_at: str
    version: str
    is_template: bool = False
    is_active: bool = False
    is_archived: bool = False


@dataclass
class ValidationResult:
    """驗證結果數據類"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]


class ConfigManager:
    """配置管理器類
    
    提供配置文件的完整生命周期管理，包括：
    - 配置文件的讀寫操作
    - 配置列表和篩選
    - 配置驗證
    - 配置備份和恢復
    - 環境變量處理
    """
    
    def __init__(self, config_dir: str = "config"):
        """初始化配置管理器
        
        Args:
            config_dir: 配置目錄路徑
        """
        self.config_dir = Path(config_dir)
        self.templates_dir = self.config_dir / "templates"
        self.active_dir = self.config_dir / "active"
        self.archived_dir = self.config_dir / "archived"
        
        # 確保目錄存在
        self._ensure_directories()
        
        # 配置驗證規則
        self._init_validation_rules()
    
    def _ensure_directories(self):
        """確保必要的目錄存在"""
        for directory in [self.templates_dir, self.active_dir, self.archived_dir]:
            directory.mkdir(parents=True, exist_ok=True)
    
    def _init_validation_rules(self):
        """初始化配置驗證規則"""
        self.validation_rules = {
            "metadata": {
                "required": ["name", "exchange", "symbol", "market_type", "strategy"],
                "validators": {
                    "exchange": ["backpack", "aster", "paradex", "lighter"],
                    "market_type": ["spot", "perp"],
                    "strategy": ["standard", "grid", "perp_grid", "maker_hedge"]
                }
            },
            "daemon_config": {
                "required": ["python_path", "script_path"],
                "validators": {
                    "max_restart_attempts": {"type": "int", "min": 1, "max": 10},
                    "restart_delay": {"type": "int", "min": 10, "max": 300},
                    "health_check_interval": {"type": "int", "min": 10, "max": 300},
                    "memory_limit_mb": {"type": "int", "min": 512, "max": 8192},
                    "cpu_limit_percent": {"type": "int", "min": 10, "max": 100}
                }
            },
            "strategy_config": {
                "validators": {
                    "grid_strategy": {
                        "grid_upper_price": {"type": "float", "min": 0},
                        "grid_lower_price": {"type": "float", "min": 0},
                        "grid_num": {"type": "int", "min": 2, "max": 200},
                        "grid_mode": {"type": "string", "enum": ["arithmetic", "geometric"]},
                        "grid_type": {"type": "string", "enum": ["neutral", "long", "short"]}
                    },
                    "perp_strategy": {
                        "max_position": {"type": "float", "min": 0.01},
                        "target_position": {"type": "float"},
                        "stop_loss": {"type": "float"},
                        "take_profit": {"type": "float"}
                    }
                }
            }
        }
    
    def expand_env_vars(self, text: Union[str, Dict, Any]) -> Any:
        """展開環境變量
        
        支持 ${VARIABLE_NAME} 格式，支持默認值 ${VARIABLE:-default}
        
        Args:
            text: 包含環境變量的文本或字典
            
        Returns:
            展開環境變量後的文本或字典
            
        Raises:
            ValueError: 當必需的敏感環境變量未設置時
        """
        if isinstance(text, dict):
            return {k: self.expand_env_vars(v) for k, v in text.items()}
        elif isinstance(text, list):
            return [self.expand_env_vars(item) for item in text]
        elif isinstance(text, str):
            pattern = r'\$\{([^}]+)\}'
            
            def replace_var(match):
                var_expr = match.group(1)
                
                # 檢查是否有默認值
                if ':-' in var_expr:
                    var_name, default_value = var_expr.split(':-', 1)
                else:
                    var_name, default_value = var_expr, match.group(0)
                
                # 檢查敏感環境變量
                sensitive_vars = ['API_KEY', 'SECRET_KEY', 'PRIVATE_KEY', 'PASSWORD', 'TOKEN']
                if any(sensitive in var_name.upper() for sensitive in sensitive_vars):
                    env_value = os.getenv(var_name)
                    if env_value is None:
                        if default_value == match.group(0):  # 沒有默認值
                            raise EnvironmentVariableError(f"必需的敏感環境變量 {var_name} 未設置", var_name=var_name)
                        else:
                            logger.warning(f"敏感環境變量 {var_name} 未設置，使用默認值")
                
                return os.getenv(var_name, default_value)
            
            return re.sub(pattern, replace_var, text)
        else:
            return text
    
    def list_configs(self, 
                   filters: Optional[Dict[str, str]] = None,
                   include_templates: bool = True,
                   include_active: bool = True,
                   include_archived: bool = True) -> List[ConfigInfo]:
        """列出配置文件
        
        Args:
            filters: 篩選條件，如 {"exchange": "backpack", "strategy": "grid"}
            include_templates: 是否包含模板
            include_active: 是否包含活躍配置
            include_archived: 是否包含歸檔配置
            
        Returns:
            配置信息列表
        """
        configs = []
        
        # 收集模板文件
        if include_templates:
            configs.extend(self._scan_directory(self.templates_dir, is_template=True))
        
        # 收集活躍配置文件
        if include_active:
            configs.extend(self._scan_directory(self.active_dir, is_active=True))
        
        # 收集歸檔配置文件
        if include_archived:
            configs.extend(self._scan_directory(self.archived_dir, is_archived=True))
        
        # 應用篩選條件
        if filters:
            configs = self._apply_filters(configs, filters)
        
        # 按名稱排序
        configs.sort(key=lambda x: x.name.lower())
        
        return configs
    
    def _scan_directory(self, directory: Path, 
                      is_template: bool = False,
                      is_active: bool = False, 
                      is_archived: bool = False) -> List[ConfigInfo]:
        """掃描目錄中的配置文件"""
        configs = []
        
        if not directory.exists():
            return configs
        
        for file_path in directory.glob("*.json"):
            try:
                config_data = self.load_config(file_path, expand_vars=False)
                metadata = config_data.get("metadata", {})
                
                config_info = ConfigInfo(
                    name=metadata.get("name", file_path.stem),
                    path=str(file_path),
                    exchange=metadata.get("exchange", ""),
                    symbol=metadata.get("symbol", ""),
                    market_type=metadata.get("market_type", ""),
                    strategy=metadata.get("strategy", ""),
                    created_at=metadata.get("created_at", ""),
                    updated_at=metadata.get("updated_at", ""),
                    version=metadata.get("version", "1.0.0"),
                    is_template=is_template,
                    is_active=is_active,
                    is_archived=is_archived
                )
                
                configs.append(config_info)
                
            except Exception as e:
                logger.warning(f"無法讀取配置文件 {file_path}: {e}")
        
        return configs
    
    def _apply_filters(self, configs: List[ConfigInfo], filters: Dict[str, str]) -> List[ConfigInfo]:
        """應用篩選條件"""
        filtered_configs = configs
        
        for key, value in filters.items():
            if key == "exchange":
                filtered_configs = [c for c in filtered_configs if c.exchange.lower() == value.lower()]
            elif key == "strategy":
                filtered_configs = [c for c in filtered_configs if c.strategy.lower() == value.lower()]
            elif key == "market_type":
                filtered_configs = [c for c in filtered_configs if c.market_type.lower() == value.lower()]
            elif key == "symbol":
                filtered_configs = [c for c in filtered_configs if c.symbol.lower() == value.lower()]
        
        return filtered_configs
    
    def load_config(self, config_path: Union[str, Path], expand_vars: bool = True) -> Dict:
        """加載配置文件
        
        Args:
            config_path: 配置文件路徑
            expand_vars: 是否展開環境變量
            
        Returns:
            配置數據字典
            
        Raises:
            FileNotFoundError: 配置文件不存在
            json.JSONDecodeError: 配置文件格式錯誤
        """
        config_path = Path(config_path)
        
        if not config_path.exists():
            raise ConfigLoadError(f"配置文件不存在: {config_path}", config_path=str(config_path))
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            if expand_vars:
                config_data = self.expand_env_vars(config_data)
            
            return config_data
            
        except json.JSONDecodeError as e:
            raise ConfigLoadError(f"配置文件格式錯誤: {e}", config_path=str(config_path))
        except EnvironmentVariableError:
            raise  # 重新拋出環境變量錯誤
        except Exception as e:
            raise ConfigLoadError(f"加載配置文件失敗: {e}", config_path=str(config_path))
    
    def save_config(self, config_path: Union[str, Path], config_data: Dict) -> bool:
        """保存配置文件
        
        Args:
            config_path: 配置文件路徑
            config_data: 配置數據字典
            
        Returns:
            是否保存成功
        """
        config_path = Path(config_path)
        
        try:
            # 確保目錄存在
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 更新時間戳
            if "metadata" in config_data:
                config_data["metadata"]["updated_at"] = datetime.now().isoformat()
            
            # 保存文件
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"配置文件已保存: {config_path}")
            return True
            
        except Exception as e:
            logger.error(f"保存配置文件失敗 {config_path}: {e}")
            raise ConfigSaveError(f"保存配置文件失敗: {e}", config_path=str(config_path))
    
    def create_from_template(self, template_name: str, target_name: str, 
                          params: Optional[Dict[str, Any]] = None) -> Dict:
        """基於模板創建配置
        
        Args:
            template_name: 模板名稱
            target_name: 目標配置名稱
            params: 參數字典，用於替換模板中的值
            
        Returns:
            創建的配置數據
            
        Raises:
            FileNotFoundError: 模板文件不存在
        """
        template_path = self.templates_dir / template_name
        
        if not template_path.exists():
            # 如果直接傳入的文件名不存在，嘗試添加 .json 後綴
            template_path = self.templates_dir / f"{template_name}.json"
            if not template_path.exists():
                raise ConfigLoadError(f"模板文件不存在: {template_name}", config_path=str(template_path))
        
        try:
            # 加載模板
            config_data = self.load_config(template_path, expand_vars=False)
        except ConfigLoadError as e:
            raise ConfigLoadError(f"加載模板失敗: {e}", config_path=str(template_path))
        
        # 應用參數
        if params:
            config_data = self._apply_params(config_data, params)
        
        # 更新元數據
        if "metadata" in config_data:
            config_data["metadata"]["name"] = target_name
            config_data["metadata"]["created_at"] = datetime.now().isoformat()
            config_data["metadata"]["updated_at"] = datetime.now().isoformat()
        
        return config_data
    
    def _apply_params(self, config_data: Dict, params: Dict[str, Any]) -> Dict:
        """應用參數到配置數據"""
        # 深拷貝配置數據
        result = json.loads(json.dumps(config_data))
        
        # 支持點號分隔的路徑，如 "strategy_config.grid_num"
        for key, value in params.items():
            self._set_nested_value(result, key, value)
        
        # 特殊處理：直接替換 metadata 中的字段
        # 這是因為有些參數需要同時更新多個位置
        for key, value in params.items():
            if key == 'symbol' and 'metadata' in result:
                result['metadata']['symbol'] = value
            elif key == 'grid_num' and 'strategy_config' in result:
                result['strategy_config']['grid_num'] = value
        
        return result
    
    def _set_nested_value(self, data: Dict, key: str, value: Any):
        """設置嵌套字典的值"""
        keys = key.split('.')
        current = data
        
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        
        current[keys[-1]] = value
    
    def validate_config(self, config_data: Dict) -> ValidationResult:
        """驗證配置數據
        
        Args:
            config_data: 配置數據字典
            
        Returns:
            驗證結果
        """
        errors = []
        warnings = []
        
        # 驗證元數據
        metadata_errors = self._validate_metadata(config_data.get("metadata", {}))
        errors.extend(metadata_errors)
        
        # 驗證守護進程配置
        daemon_errors = self._validate_daemon_config(config_data.get("daemon_config", {}))
        errors.extend(daemon_errors)
        
        # 驗證交易所配置
        exchange_errors = self._validate_exchange_config(config_data.get("exchange_config", {}))
        errors.extend(exchange_errors)
        
        # 驗證策略配置
        strategy_errors, strategy_warnings = self._validate_strategy_config(
            config_data.get("metadata", {}),
            config_data.get("strategy_config", {})
        )
        errors.extend(strategy_errors)
        warnings.extend(strategy_warnings)
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def _validate_metadata(self, metadata: Dict) -> List[str]:
        """驗證元數據"""
        errors = []
        rules = self.validation_rules["metadata"]
        
        # 檢查必需字段
        for field in rules["required"]:
            if field not in metadata:
                errors.append(f"缺少必需的元數據字段: {field}")
        
        # 檢查字段值
        for field, valid_values in rules["validators"].items():
            if field in metadata and metadata[field] not in valid_values:
                errors.append(f"無效的 {field}: {metadata[field]}，有效值: {valid_values}")
        
        return errors
    
    def _validate_daemon_config(self, daemon_config: Dict) -> List[str]:
        """驗證守護進程配置"""
        errors = []
        rules = self.validation_rules["daemon_config"]
        
        # 檢查必需字段
        for field in rules["required"]:
            if field not in daemon_config:
                errors.append(f"缺少必需的守護進程配置字段: {field}")
        
        # 檢查字段值
        for field, rule in rules["validators"].items():
            if field in daemon_config:
                value = daemon_config[field]
                
                # 類型檢查
                if rule["type"] == "int":
                    try:
                        value = int(value)
                    except (ValueError, TypeError):
                        errors.append(f"{field} 必須是整數: {value}")
                        continue
                    
                    # 範圍檢查
                    if "min" in rule and value < rule["min"]:
                        errors.append(f"{field} 不能小於 {rule['min']}: {value}")
                    if "max" in rule and value > rule["max"]:
                        errors.append(f"{field} 不能大於 {rule['max']}: {value}")
        
        return errors
    
    def _validate_exchange_config(self, exchange_config: Dict) -> List[str]:
        """驗證交易所配置"""
        errors = []
        
        # 檢查 API 密鑰是否使用環境變量
        for field in ["api_key", "secret_key"]:
            if field in exchange_config:
                value = exchange_config[field]
                if not isinstance(value, str) or not value.startswith("${"):
                    errors.append(f"{field} 應該使用環境變量格式: ${{VARIABLE_NAME}}")
        
        return errors
    
    def _validate_strategy_config(self, metadata: Dict, strategy_config: Dict) -> Tuple[List[str], List[str]]:
        """驗證策略配置"""
        errors = []
        warnings = []
        
        strategy = metadata.get("strategy", "")
        
        if strategy == "grid" or strategy == "perp_grid":
            grid_rules = self.validation_rules["strategy_config"]["validators"]["grid_strategy"]
            
            # 存儲已驗證的浮點數值，避免重複轉換
            validated_floats = {}
            
            # 網格策略特定驗證
            for field, rule in grid_rules.items():
                if field in strategy_config:
                    value = strategy_config[field]
                    
                    if rule["type"] == "float":
                        try:
                            float_value = float(value)
                            validated_floats[field] = float_value  # 存儲已驗證的值
                        except (ValueError, TypeError):
                            errors.append(f"{field} 必須是數字: {value}")
                            continue
                        
                        if "min" in rule and float_value < rule["min"]:
                            errors.append(f"{field} 不能小於 {rule['min']}: {float_value}")
                    
                    elif rule["type"] == "int":
                        try:
                            value = int(value)
                        except (ValueError, TypeError):
                            errors.append(f"{field} 必須是整數: {value}")
                            continue
                        
                        if "min" in rule and value < rule["min"]:
                            errors.append(f"{field} 不能小於 {rule['min']}: {value}")
                        if "max" in rule and value > rule["max"]:
                            errors.append(f"{field} 不能大於 {rule['max']}: {value}")
                    
                    elif rule["type"] == "string" and "enum" in rule:
                        if value not in rule["enum"]:
                            errors.append(f"無效的 {field}: {value}，有效值: {rule['enum']}")
            
            # 網格邏輯驗證 - 使用已驗證的值
            if ("grid_upper_price" in validated_floats and
                "grid_lower_price" in validated_floats):
                upper = validated_floats["grid_upper_price"]
                lower = validated_floats["grid_lower_price"]
                
                if upper <= lower:
                    errors.append("grid_upper_price 必須大於 grid_lower_price")
        
        elif strategy in ["standard", "perp_standard", "maker_hedge"]:
            perp_rules = self.validation_rules["strategy_config"]["validators"]["perp_strategy"]
            
            # 永續策略特定驗證
            for field, rule in perp_rules.items():
                if field in strategy_config:
                    value = strategy_config[field]
                    
                    if rule["type"] == "float":
                        try:
                            value = float(value)
                        except (ValueError, TypeError):
                            errors.append(f"{field} 必須是數字: {value}")
                            continue
                        
                        if field == "max_position" and value <= 0:
                            errors.append("max_position 必須大於 0")
                        
                        if field == "stop_loss" and value is not None and value >= 0:
                            warnings.append("stop_loss 應該是負值")
                        
                        if field == "take_profit" and value is not None and value <= 0:
                            warnings.append("take_profit 應該是正值")
        
        return errors, warnings
    
    def delete_config(self, config_path: Union[str, Path]) -> bool:
        """刪除配置文件
        
        Args:
            config_path: 配置文件路徑
            
        Returns:
            是否刪除成功
        """
        config_path = Path(config_path)
        
        if not config_path.exists():
            logger.warning(f"配置文件不存在: {config_path}")
            return False
        
        try:
            config_path.unlink()
            logger.info(f"配置文件已刪除: {config_path}")
            return True
            
        except Exception as e:
            logger.error(f"刪除配置文件失敗 {config_path}: {e}")
            raise ConfigError(f"刪除配置文件失敗: {e}", config_path=str(config_path))
    
    def backup_config(self, config_path: Union[str, Path]) -> Optional[str]:
        """備份配置文件
        
        Args:
            config_path: 配置文件路徑
            
        Returns:
            備份文件路徑，失敗時返回 None
        """
        config_path = Path(config_path)
        
        if not config_path.exists():
            logger.warning(f"配置文件不存在，無法備份: {config_path}")
            return None
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"{config_path.stem}_backup_{timestamp}.json"
            backup_path = self.archived_dir / backup_filename
            
            # 複製文件
            shutil.copy2(config_path, backup_path)
            
            # 計算並保存校驗和
            checksum = self._calculate_checksum(config_path)
            checksum_path = backup_path.with_suffix('.json.checksum')
            with open(checksum_path, 'w') as f:
                f.write(checksum)
            
            logger.info(f"配置文件已備份: {backup_path}")
            logger.debug(f"備份文件校驗和: {checksum}")
            
            return str(backup_path)
            
        except Exception as e:
            logger.error(f"備份配置文件失敗 {config_path}: {e}")
            raise ConfigBackupError(f"備份配置文件失敗: {e}", config_path=str(config_path))
    
    def restore_config(self, backup_path: Union[str, Path], target_path: Optional[Union[str, Path]] = None) -> bool:
        """恢復配置文件
        
        Args:
            backup_path: 備份文件路徑
            target_path: 目標路徑，如果為 None 則使用原路徑
            
        Returns:
            是否恢復成功
        """
        backup_path = Path(backup_path)
        
        if not backup_path.exists():
            raise ConfigRestoreError(f"備份文件不存在: {backup_path}")
        
        if target_path is None:
            # 從備份文件名推斷原路徑
            original_name = backup_path.stem.replace("_backup_", "").replace(".json", "")
            target_path = self.active_dir / f"{original_name}.json"
        
        target_path = Path(target_path)
        
        try:
            # 驗證備份文件完整性
            checksum_path = backup_path.with_suffix('.json.checksum')
            if checksum_path.exists():
                with open(checksum_path, 'r') as f:
                    expected_checksum = f.read().strip()
                
                actual_checksum = self._calculate_checksum(backup_path)
                if expected_checksum != actual_checksum:
                    logger.error(f"備份文件校驗和不匹配，可能已損壞: {backup_path}")
                    logger.error(f"期望校驗和: {expected_checksum}")
                    logger.error(f"實際校驗和: {actual_checksum}")
                    raise ConfigRestoreError(f"備份文件校驗和不匹配", config_path=str(backup_path),
                                          expected=expected_checksum, actual=actual_checksum)
                else:
                    logger.debug(f"備份文件校驗和驗證通過: {actual_checksum}")
            else:
                logger.warning(f"備份文件缺少校驗和文件，跳過完整性檢查: {backup_path}")
            
            # 確保目標目錄存在
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            shutil.copy2(backup_path, target_path)
            logger.info(f"配置文件已恢復: {target_path}")
            
            return True
            
        except ConfigRestoreError:
            raise  # 重新拋出配置恢復錯誤
        except Exception as e:
            raise ConfigRestoreError(f"恢復配置文件失敗: {e}", config_path=str(backup_path))
    
    def get_config_path(self, config_name: str, config_type: str = "active") -> Path:
        """獲取配置文件路徑
        
        Args:
            config_name: 配置名稱
            config_type: 配置類型 ("template", "active", "archived")
            
        Returns:
            配置文件路徑
        """
        if config_type == "template":
            return self.templates_dir / f"{config_name}.json"
        elif config_type == "active":
            return self.active_dir / f"{config_name}.json"
        elif config_type == "archived":
            return self.archived_dir / f"{config_name}.json"
        else:
            raise ValueError(f"無效的配置類型: {config_type}")
    
    def list_templates(self) -> List[str]:
        """列出所有模板文件名稱
        
        Returns:
            模板文件名稱列表
        """
        if not self.templates_dir.exists():
            return []
        
        templates = []
        for file_path in self.templates_dir.glob("*.json"):
            templates.append(file_path.name)
        
        return sorted(templates)
    
    def list_active_configs(self) -> List[str]:
        """列出所有活躍配置文件名稱
        
        Returns:
            活躍配置文件名稱列表
        """
        if not self.active_dir.exists():
            return []
        
        configs = []
        for file_path in self.active_dir.glob("*.json"):
            configs.append(file_path.name)
        
        return sorted(configs)
    
    def list_archived_configs(self) -> List[str]:
        """列出所有歸檔配置文件名稱
        
        Returns:
            歸檔配置文件名稱列表
        """
        if not self.archived_dir.exists():
            return []
        
        configs = []
        for file_path in self.archived_dir.glob("*.json"):
            configs.append(file_path.name)
        
        return sorted(configs)
    
    def create_config_from_template(self, template_name: str, output_name: str, **params) -> str:
        """從模板創建配置文件
        
        Args:
            template_name: 模板文件名稱
            output_name: 輸出配置文件名稱
            **params: 替換參數
            
        Returns:
            創建的配置文件路徑
        """
        # 創建配置數據
        config_data = self.create_from_template(template_name, output_name, params)
        
        # 保存到活躍配置目錄
        output_path = self.active_dir / output_name
        
        if self.save_config(output_path, config_data):
            return str(output_path)
        else:
            raise ConfigSaveError(f"保存配置文件失敗", config_path=str(output_path))
    
    def validate_config_file(self, config_path: Union[str, Path]) -> ValidationResult:
        """驗證配置文件
        
        Args:
            config_path: 配置文件路徑
            
        Returns:
            驗證結果
        """
        config_data = self.load_config(config_path, expand_vars=False)
        return self.validate_config(config_data)
    
    def _calculate_checksum(self, file_path: Path) -> str:
        """計算文件的校驗和
        
        Args:
            file_path: 文件路徑
            
        Returns:
            文件的 SHA256 校驗和
        """
        import hashlib
        
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()