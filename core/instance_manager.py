"""
實例管理器 - 統一管理多個交易機器人實例
提供實例註冊、查詢、清理等功能
"""
import json
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime
import psutil


class InstanceRegistry:
    """實例註冊表"""

    def __init__(self, registry_file: str = "logs/instances.json"):
        """
        初始化實例註冊表

        Args:
            registry_file: 註冊表文件路徑
        """
        self.registry_file = Path(registry_file)
        self.registry_file.parent.mkdir(parents=True, exist_ok=True)

    def register(self, instance_id: str, info: Dict[str, Any]) -> None:
        """
        註冊實例

        Args:
            instance_id: 實例ID
            info: 實例信息字典
        """
        registry = self.load()
        registry[instance_id] = {
            **info,
            "registered_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat()
        }
        self.save(registry)

    def unregister(self, instance_id: str) -> bool:
        """
        註銷實例

        Args:
            instance_id: 實例ID

        Returns:
            bool: 是否成功註銷
        """
        registry = self.load()
        if instance_id in registry:
            del registry[instance_id]
            self.save(registry)
            return True
        return False

    def update(self, instance_id: str, info: Dict[str, Any]) -> bool:
        """
        更新實例信息

        Args:
            instance_id: 實例ID
            info: 要更新的信息

        Returns:
            bool: 是否成功更新
        """
        registry = self.load()
        if instance_id in registry:
            registry[instance_id].update(info)
            registry[instance_id]["last_updated"] = datetime.now().isoformat()
            self.save(registry)
            return True
        return False

    def get(self, instance_id: str) -> Optional[Dict[str, Any]]:
        """
        獲取實例信息

        Args:
            instance_id: 實例ID

        Returns:
            Dict or None: 實例信息字典，不存在則返回None
        """
        registry = self.load()
        return registry.get(instance_id)

    def load(self) -> Dict[str, Any]:
        """
        加載註冊表

        Returns:
            Dict: 註冊表字典
        """
        if not self.registry_file.exists():
            return {}

        try:
            with open(self.registry_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    def save(self, registry: Dict[str, Any]) -> None:
        """
        保存註冊表

        Args:
            registry: 註冊表字典
        """
        with open(self.registry_file, 'w', encoding='utf-8') as f:
            json.dump(registry, f, indent=2, ensure_ascii=False)

    def list_instances(self, include_dead: bool = False) -> List[Dict[str, Any]]:
        """
        列出所有實例

        Args:
            include_dead: 是否包含已停止的實例

        Returns:
            List[Dict]: 實例信息列表
        """
        registry = self.load()
        instances = []

        for instance_id, info in registry.items():
            # 檢查進程是否還在運行
            is_alive = self._check_instance_alive(info)

            if not include_dead and not is_alive:
                continue

            instances.append({
                "instance_id": instance_id,
                "is_alive": is_alive,
                **info
            })

        # 按實例ID排序
        instances.sort(key=lambda x: x['instance_id'])
        return instances

    def _check_instance_alive(self, info: Dict[str, Any]) -> bool:
        """
        檢查實例是否存活

        Args:
            info: 實例信息

        Returns:
            bool: 是否存活
        """
        try:
            pid = info.get('pid')
            if not pid:
                return False

            if not psutil.pid_exists(pid):
                return False

            process = psutil.Process(pid)
            return process.is_running() and process.status() != psutil.STATUS_ZOMBIE

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return False
        except Exception:
            return False

    def cleanup_dead_instances(self) -> int:
        """
        清理已死亡的實例記錄

        Returns:
            int: 清理的實例數量
        """
        registry = self.load()
        dead_instances = []

        for instance_id, info in registry.items():
            if not self._check_instance_alive(info):
                dead_instances.append(instance_id)

        for instance_id in dead_instances:
            del registry[instance_id]

        if dead_instances:
            self.save(registry)

        return len(dead_instances)

    def get_instance_by_port(self, port: int) -> Optional[Dict[str, Any]]:
        """
        根據端口號查找實例

        Args:
            port: Web端口號

        Returns:
            Dict or None: 實例信息，不存在則返回None
        """
        registry = self.load()
        for instance_id, info in registry.items():
            if info.get('web_port') == port:
                return {
                    "instance_id": instance_id,
                    **info
                }
        return None

    def get_running_instances(self) -> List[Dict[str, Any]]:
        """
        獲取所有運行中的實例

        Returns:
            List[Dict]: 運行中的實例列表
        """
        return self.list_instances(include_dead=False)

    def count_instances(self, alive_only: bool = True) -> int:
        """
        統計實例數量

        Args:
            alive_only: 是否只統計運行中的實例

        Returns:
            int: 實例數量
        """
        instances = self.list_instances(include_dead=not alive_only)
        return len(instances)

    def exists(self, instance_id: str) -> bool:
        """
        檢查實例是否存在

        Args:
            instance_id: 實例ID

        Returns:
            bool: 是否存在
        """
        registry = self.load()
        return instance_id in registry


class InstanceManager:
    """實例管理器 - 提供更高級的管理功能"""

    def __init__(self):
        self.registry = InstanceRegistry()

    def get_instance_stats(self, instance_id: str) -> Optional[Dict[str, Any]]:
        """
        獲取實例的詳細統計信息

        Args:
            instance_id: 實例ID

        Returns:
            Dict or None: 統計信息
        """
        info = self.registry.get(instance_id)
        if not info:
            return None

        stats = {
            "instance_id": instance_id,
            "is_alive": self.registry._check_instance_alive(info),
            **info
        }

        # 獲取進程詳細信息
        pid = info.get('pid')
        if pid and psutil.pid_exists(pid):
            try:
                process = psutil.Process(pid)
                stats["process_info"] = {
                    "name": process.name(),
                    "status": process.status(),
                    "cpu_percent": process.cpu_percent(interval=0.1),
                    "memory_mb": process.memory_info().rss / 1024 / 1024,
                    "num_threads": process.num_threads(),
                    "create_time": datetime.fromtimestamp(process.create_time()).isoformat()
                }
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        return stats

    def get_all_stats(self) -> List[Dict[str, Any]]:
        """
        獲取所有實例的統計信息

        Returns:
            List[Dict]: 所有實例的統計信息
        """
        instances = self.registry.list_instances(include_dead=True)
        stats_list = []

        for inst in instances:
            instance_id = inst.get('instance_id')
            if instance_id:
                stats = self.get_instance_stats(instance_id)
                if stats:
                    stats_list.append(stats)

        return stats_list

    def validate_instance_config(self, instance_id: str) -> Dict[str, Any]:
        """
        驗證實例配置

        Args:
            instance_id: 實例ID

        Returns:
            Dict: 驗證結果 {valid: bool, errors: List[str], warnings: List[str]}
        """
        info = self.registry.get(instance_id)
        if not info:
            return {
                "valid": False,
                "errors": [f"實例 {instance_id} 不存在"],
                "warnings": []
            }

        errors = []
        warnings = []

        # 檢查必要字段
        required_fields = ['config_file', 'pid', 'log_dir', 'web_port']
        for field in required_fields:
            if field not in info:
                errors.append(f"缺少必要字段: {field}")

        # 檢查配置文件是否存在
        config_file = info.get('config_file')
        if config_file and not Path(config_file).exists():
            warnings.append(f"配置文件不存在: {config_file}")

        # 檢查日誌目錄
        log_dir = info.get('log_dir')
        if log_dir and not Path(log_dir).exists():
            warnings.append(f"日誌目錄不存在: {log_dir}")

        # 檢查進程狀態
        if not self.registry._check_instance_alive(info):
            warnings.append("進程未運行或已停止")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
