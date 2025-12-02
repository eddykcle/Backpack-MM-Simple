# 简化多实例管理架构

## 目标

同时运行多个 grid bot 实例，使用统一的 `daemon_manager.py` 命令行入口。

## 修改范围

### 1. 修改 `core/daemon_manager.py`（小改动）

让 `TradingBotDaemon` 复用 `InstanceRegistry` 类，消除代码重复：

```python
# 在文件开头添加导入
from core.instance_manager import InstanceRegistry

class TradingBotDaemon:
    def __init__(self, ...):
        # ... 现有代码 ...
        self.registry = InstanceRegistry()  # 新增
    
    def _register_instance(self):
        """使用 InstanceRegistry 注册"""
        self.registry.register(self.instance_id, {
            "config_file": str(self.config_file),
            "pid": os.getpid(),
            "log_dir": str(self.log_dir),
            "web_port": self.config.get("web_port"),
            "started_at": datetime.now().isoformat(),
            "status": "starting"
        })
    
    def _unregister_instance(self):
        """使用 InstanceRegistry 注销"""
        self.registry.unregister(self.instance_id)
```

### 2. 保留 `core/instance_manager.py`

作为底层库，无需修改。

### 3. 删除 `cli/instance_cli.py`

不需要此文件，功能已被 `daemon_manager.py` 覆盖。

## 使用方式（无变化）

```bash
# 启动实例 1
python core/daemon_manager.py start -c config/active/bp_sol_01.json -d

# 启动实例 2
python core/daemon_manager.py start -c config/active/bp_eth_02.json -d

# 列出所有实例
python core/daemon_manager.py list

# 停止实例
python core/daemon_manager.py stop -c config/active/bp_sol_01.json

# 查看状态
python core/daemon_manager.py status -c config/active/bp_sol_01.json
```

## 文件修改清单

| 文件 | 操作 | 工作量 |

|-----|-----|-------|

| `core/daemon_manager.py` | 小修改 | ~30 行 |

| `core/instance_manager.py` | 保留 | 无 |

| `cli/instance_cli.py` | 删除 | 无 |

## Memory
只需要能同時啟動/停止/列出多個 grid bot 實例 (最簡方案)

统一入口：所有功能都通過 daemon_manager.py

方案 A：统一命令入口（推荐）
把所有功能合并到 daemon_manager.py：
# 实例生命周期
python daemon_manager.py start -c config/bp_sol_01.jsonpython daemon_manager.py stop -c config/bp_sol_01.json# 多实例管理（现在也在同一个工具）
python daemon_manager.py list       # 列出所有实例python daemon_manager.py cleanup     # 清理死亡实例python daemon_manager.py stop-all    # 停止所有实例

# 現在的設計
你的直觉是对的，主要问题有：
1. 功能重叠
两个文件都有 list 功能：
# daemon_manager.py (line 320-321)parser.add_argument('action', choices=['start', 'stop', 'restart', 'status', 'list'], ...)# instance_cli.py (line 608)subparsers.add_parser('list', help='列出所有實例')
2. 用户体验碎片化
用户需要记住：
启动实例 → 用 daemon_manager.py start
列出实例 → 用 daemon_manager.py list 或 instance_cli.py list？
清理实例 → 只能用 instance_cli.py cleanup
3. 架构层次不清晰
InstanceRegistry 类定义在 instance_manager.py 中，但 daemon_manager.py 内部又重新实现了 _register_instance() 方法，没有复用。

# 代码 Review 总结
当前文件结构
文件	行数	职责
core/daemon_manager.py	953	单实例生命周期管理 + list 命令
core/instance_manager.py	358	InstanceRegistry 和 InstanceManager 类
cli/instance_cli.py	343	实例管理 CLI（list/cleanup/stats/validate/info）

发现的问题
1. 代码重复 - 实例注册逻辑
daemon_manager.py 自己实现了注册逻辑，没有复用 InstanceRegistry：
daemon_manager.pyLines 282-338
    def _register_instance(self):        """註冊實例到全局註冊表"""        try:            registry_file = Path("logs/instances.json")            registry = {}            # 加載現有註冊表            if registry_file.exists():                try:                    with open(registry_file, 'r') as f:                        registry = json.load(f)                # ... 重复实现了 InstanceRegistry.load() 的功能
而 instance_manager.py 已经有完整的实现：
instance_manager.pyLines 90-104
    def load(self) -> Dict[str, Any]:        """加載註冊表"""        if not self.registry_file.exists():            return {}        try:            with open(self.registry_file, 'r', encoding='utf-8') as f:                return json.load(f)        except Exception:            return {}
2. 功能重复 - list 命令
daemon_manager.py 有 list_instances() 函数：
daemon_manager.pyLines 873-909
def list_instances():    """列出所有運行中的實例"""
instance_cli.py 也有 list_instances_cmd()：
instance_cli.pyLines 27-65
def list_instances_cmd(args):    """列出所有實例"""
3. instance_cli.py 独有的功能未整合
以下功能只在 instance_cli.py 中存在：
cleanup - 清理已停止的实例记录（带确认）
stats - 显示实例统计信息（CPU、内存等）
validate - 验证实例配置
info - 显示实例详细信息