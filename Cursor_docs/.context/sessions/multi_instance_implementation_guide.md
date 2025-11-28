# 多實例交易機器人系統：綜合實施指南（修訂版）

## 📋 文檔信息

- **日期**：2025-11-28
- **版本**：2.0（Claude Code 審閱修訂版）
- **目標**：實現多個 Perp Grid Bot 實例並發運行，每個實例擁有獨立的策略、配置、API 密鑰和資源隔離

---

## 1. 現狀分析與架構評估

### 1.1 已完成的基礎設施 ✅

經過代碼審查，以下功能已經完善：

1. **多配置管理系統**：
   - `ConfigManager` (core/config_manager.py) 已實現完整的配置管理功能
   - 支持 `config/templates/`、`config/active/`、`config/archived/` 目錄結構
   - 環境變量展開與驗證機制完善

2. **守護進程基礎**：
   - `TradingBotDaemon` (core/daemon_manager.py) 已實現進程監控、自動重啟、健康檢查
   - 支持新舊兩種配置格式（傳統單文件和多配置格式）

3. **日誌管理系統**：
   - 結構化日誌系統 (core/log_manager.py)
   - 自動日誌輪轉和清理

### 1.2 多實例運行的關鍵瓶頸 ⚠️

經過深入分析，發現以下**必須解決**的問題：

#### 🔴 Critical Issues（必須解決）

1. **PID 文件衝突**
   - 現狀：所有實例共用 `logs/daemon.pid` 和 `logs/bot.pid`
   - 影響：第二個實例會覆蓋第一個實例的 PID，導致狀態混亂
   - 位置：`daemon_manager.py` line 51, 273

2. **Web 服務器端口衝突**
   - 現狀：所有實例默認使用 port 5000
   - 影響：第二個實例無法啟動 Web 界面
   - 位置：`web/server.py` line 1051-1077, `run.py` line 263

3. **日誌目錄共享**
   - 現狀：所有實例寫入相同的日誌目錄 `logs/YYYY-MM-DD/`
   - 影響：日誌交錯，難以排查問題，可能有文件鎖衝突
   - 位置：`daemon_manager.py` line 592-597

4. **數據庫文件衝突**
   - 現狀：所有實例共用同一個 SQLite 數據庫 `trade.db`
   - 影響：數據交錯、鎖衝突、數據不一致
   - 需要檢查：`database/db.py`

5. **Web 服務器全局狀態**
   - 現狀：Web 服務器使用全局變量存儲策略實例 (`current_strategy`)
   - 影響：多實例情況下只能控制一個實例
   - 位置：`web/server.py` line 43-68, 391-403

#### 🟡 Important Issues（建議解決）

6. **缺少實例註冊機制**
   - 無法列出當前運行的所有實例
   - 無法通過統一接口管理實例

7. **實例 ID 衝突防護**
   - 沒有檢查同一 instance_id 是否已經在運行

8. **命令行工具不支持實例管理**
   - 現有 `daemon_manager.py` 的 CLI 不支持 `--instance-id` 參數
   - 沒有 `list-instances` 命令

---

## 2. 技術方案設計

### 2.1 方案選擇：輕量級獨立實例方案

**選擇理由**：
- ✅ 實施簡單，風險低
- ✅ 實例完全隔離，一個崩潰不影響其他
- ✅ 利用現有架構，改動最小
- ✅ 符合原始文檔的設計思路

**架構概述**：
```
每個實例 = 獨立的守護進程 + 獨立的 run.py 子進程 + 獨立的 Web 服務器

實例 A (bp_sol_01)                     實例 B (bp_eth_02)
├─ daemon_manager.py (PID: 1001)      ├─ daemon_manager.py (PID: 2001)
│  ├─ logs/bp_sol_01/daemon.pid       │  ├─ logs/bp_eth_02/daemon.pid
│  └─ 監控 run.py (PID: 1002)         │  └─ 監控 run.py (PID: 2002)
├─ run.py --symbol SOL_USDC...        ├─ run.py --symbol ETH_USDC...
│  ├─ logs/bp_sol_01/bot.pid          │  ├─ logs/bp_eth_02/bot.pid
│  └─ database/bp_sol_01.db           │  └─ database/bp_eth_02.db
└─ Web UI (port 5001)                 └─ Web UI (port 5002)
```

### 2.2 實例 ID 規則

**優先級順序**：
1. 命令行參數：`--instance-id <id>`（最高優先級）
2. 配置文件：`metadata.instance_id`
3. 配置文件名：去掉 `.json` 後綴（例如 `bp_sol_01.json` → `bp_sol_01`）

**命名規範建議**：
```
<exchange>_<symbol>_<number>
例如：
- bp_sol_01  (Backpack SOL 實例 1)
- bp_eth_02  (Backpack ETH 實例 2)
- aster_btc_01 (Aster BTC 實例 1)
```

### 2.3 資源隔離方案

| 資源類型 | 隔離路徑 | 配置方式 |
|---------|---------|---------|
| 守護進程 PID | `logs/{instance_id}/daemon.pid` | 自動生成 |
| Bot 進程 PID | `logs/{instance_id}/bot.pid` | 自動生成 |
| 日誌目錄 | `logs/{instance_id}/YYYY-MM-DD/` | daemon_config.log_dir |
| 數據庫文件 | `database/{instance_id}.db` | daemon_config.db_path |
| Web 端口 | 5001, 5002, 5003... | daemon_config.web_port |

---

## 3. 詳細實施步驟

### Phase 1：配置結構擴展（0.5 天）

#### 1.1 更新配置文件模板

在 `config/templates/` 和 `config/active/` 中的配置文件添加以下字段：

```json
{
  "metadata": {
    "name": "Backpack SOL Grid",
    "instance_id": "bp_sol_01",  // [新增] 實例唯一標識
    "exchange": "backpack",
    "symbol": "SOL_USDC_PERP",
    "market_type": "perp",
    "strategy": "perp_grid",
    "version": "1.0.0"
  },
  "daemon_config": {
    "python_path": ".venv/bin/python3",
    "script_path": "run.py",
    "working_dir": ".",
    "log_dir": "logs/bp_sol_01",           // [新增] 實例專用日誌目錄
    "db_path": "database/bp_sol_01.db",    // [新增] 實例專用數據庫
    "web_port": 5001,                       // [新增] Web 服務器端口
    "max_restart_attempts": 3,
    "restart_delay": 60,
    "health_check_interval": 30,
    "memory_limit_mb": 2048,
    "cpu_limit_percent": 80,
    "auto_restart": true,
    "log_cleanup_interval": 86400,
    "log_retention_days": 2,
    "bot_args": [...]
  },
  "exchange_config": {...},
  "strategy_config": {...}
}
```

**自動回退機制**：
- 如果配置中未指定 `log_dir`，自動設為 `logs/{instance_id}`
- 如果未指定 `db_path`，自動設為 `database/{instance_id}.db`
- 如果未指定 `web_port`，自動從 5001 開始搜索可用端口

#### 1.2 創建示例配置

創建 `config/active/example_multi_instance.json` 作為參考。

---

### Phase 2：守護進程管理器改造（1 天）

#### 2.1 修改 `core/daemon_manager.py`

**變更清單**：

1. **`__init__` 方法**（line 30-54）：
   ```python
   def __init__(self, config_file: str = "config/daemon_config.json", instance_id: str = None):
       self.config_file = Path(config_file)
       self.is_multi_config = self._is_multi_config_format(config_file)

       # 確定實例 ID（優先級：參數 > 配置 > 文件名）
       if instance_id:
           self.instance_id = instance_id
       elif self.is_multi_config:
           # 從配置文件讀取
           config_data = self._load_config_for_instance_id()
           self.instance_id = config_data.get('metadata', {}).get('instance_id') or self.config_file.stem
       else:
           self.instance_id = self.config_file.stem

       # 實例專用日誌目錄
       self.log_dir = Path(f"logs/{self.instance_id}")
       self.log_dir.mkdir(parents=True, exist_ok=True)

       # 初始化日誌系統
       self.logger = get_logger("trading_bot_daemon", log_dir=str(self.log_dir))
       self.process_manager = ProcessManager(str(self.log_dir))

       # 加載配置
       self.config = self.load_config()

       # 信號處理
       self.running = True
       signal.signal(signal.SIGTERM, self._signal_handler)
       signal.signal(signal.SIGINT, self._signal_handler)

       # 子進程管理
       self._bot_process: Optional[subprocess.Popen] = None
       self._bot_pid_file = self.log_dir / "bot.pid"  # 實例專用

       # 註冊退出清理
       atexit.register(self._cleanup_bot_process)

       # 註冊實例
       self._register_instance()
   ```

2. **新增實例註冊方法**：
   ```python
   def _register_instance(self):
       """註冊實例到全局註冊表"""
       registry_file = Path("logs/instances.json")
       registry = {}

       if registry_file.exists():
           with open(registry_file, 'r') as f:
               registry = json.load(f)

       registry[self.instance_id] = {
           "config_file": str(self.config_file),
           "pid": os.getpid(),
           "log_dir": str(self.log_dir),
           "web_port": self.config.get("web_port"),
           "started_at": datetime.now().isoformat(),
           "status": "starting"
       }

       registry_file.parent.mkdir(exist_ok=True)
       with open(registry_file, 'w') as f:
           json.dump(registry, f, indent=2)

   def _unregister_instance(self):
       """從全局註冊表移除實例"""
       registry_file = Path("logs/instances.json")
       if not registry_file.exists():
           return

       with open(registry_file, 'r') as f:
           registry = json.load(f)

       if self.instance_id in registry:
           del registry[self.instance_id]

       with open(registry_file, 'w') as f:
           json.dump(registry, f, indent=2)
   ```

3. **修改日誌輸出路徑**（line 592-597）：
   ```python
   # 使用實例專用日誌目錄
   current_date = datetime.now().strftime('%Y-%m-%d')
   date_dir = self.log_dir / current_date  # 已經是實例專用的
   date_dir.mkdir(parents=True, exist_ok=True)

   stdout_log = date_dir / "bot_stdout.log"
   stderr_log = date_dir / "bot_stderr.log"
   ```

4. **修改 `stop()` 方法**（line 286-321）：
   ```python
   def stop(self) -> bool:
       """停止守護進程"""
       try:
           # 先清理子進程
           self._cleanup_bot_process()

           # 停止所有由守護進程啟動的 run.py 子進程
           self._stop_old_bot_processes()

           # 檢查守護進程是否在運行
           if not self.process_manager.is_running():
               self.logger.warning("守護進程未在運行")
               # 清理註冊
               self._unregister_instance()
               return False

           pid = self.process_manager.get_pid()
           self.logger.info("正在停止守護進程", pid=pid)

           # 停止守護進程
           success = self.process_manager.stop_process()

           if success:
               self.logger.info("守護進程已停止")
               # 清理註冊
               self._unregister_instance()

           return success
       except Exception as e:
           self.logger.error("停止守護進程失敗", error=str(e), exc_info=True)
           return False
   ```

5. **修改 `main()` 函數**（line 756-790）：
   ```python
   def main():
       """主函數"""
       parser = argparse.ArgumentParser(description='交易機器人守護進程管理器')
       parser.add_argument('action', choices=['start', 'stop', 'restart', 'status', 'list'],
                          help='操作: start, stop, restart, status, list')
       parser.add_argument('--daemon', '-d', action='store_true', help='以守護進程方式運行')
       parser.add_argument('--config', '-c', default='config/daemon_config.json',
                          help='配置文件路徑')
       parser.add_argument('--instance-id', help='實例 ID（可選，默認從配置文件讀取）')

       args = parser.parse_args()

       if args.action == 'list':
           list_instances()
           sys.exit(0)

       # 創建守護進程管理器
       daemon = TradingBotDaemon(args.config, instance_id=args.instance_id)

       # ... 其餘代碼保持不變

   def list_instances():
       """列出所有運行中的實例"""
       registry_file = Path("logs/instances.json")
       if not registry_file.exists():
           print("沒有運行中的實例")
           return

       with open(registry_file, 'r') as f:
           registry = json.load(f)

       if not registry:
           print("沒有運行中的實例")
           return

       print(f"{'實例ID':<20} {'PID':<10} {'Web端口':<10} {'配置文件':<40} {'啟動時間':<25}")
       print("-" * 105)
       for instance_id, info in registry.items():
           print(f"{instance_id:<20} {info['pid']:<10} {info.get('web_port', 'N/A'):<10} "
                 f"{info['config_file']:<40} {info['started_at']:<25}")
   ```

#### 2.2 修改 `core/log_manager.py`

確保日誌系統支持實例級別的目錄隔離（檢查現有實現是否已支持）。

---

### Phase 3：數據庫隔離（0.5 天）

#### 3.1 檢查並修改 `database/db.py`

確保 `Database` 類的 `__init__` 方法接受 `db_path` 參數：

```python
class Database:
    def __init__(self, db_path: str = "database/trade.db"):
        self.db_path = db_path
        self.conn = None
        self.init_database()
```

#### 3.2 確保策略初始化時傳遞正確的數據庫路徑

在 `run.py` 中，策略實例化時需要從配置中讀取 `db_path`。

---

### Phase 4：Web 服務器改造（1 天）

#### 4.1 修改 `web/server.py`

**方案選擇**：保持每個實例有獨立的 Web UI（簡單方案）

1. **動態端口支持**（line 1051-1077）：
   ```python
   def run_server(host='0.0.0.0', port=5000, debug=False):
       """運行Web服務器"""
       # 優先從環境變量讀取
       web_host = os.getenv('WEB_HOST', host)
       web_port = int(os.getenv('WEB_PORT', port))
       web_debug = os.getenv('WEB_DEBUG', 'false').lower() in ('true', '1', 'yes')

       host = web_host
       port = web_port
       debug = web_debug

       # 檢查端口是否可用（現有邏輯保持）
       if not is_port_available(host, port):
           logger.warning(f"端口 {port} 已被佔用，正在尋找可用端口...")
           new_port = find_available_port(host, port + 1, 6000)
           if new_port:
               logger.info(f"找到可用端口: {new_port}")
               port = new_port
           else:
               logger.error("無法找到可用端口")
               return

       logger.info(f"啟動Web服務器於 http://{host}:{port}")
       socketio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)
   ```

2. **run.py 中傳遞端口參數**（line 139-162）：
   ```python
   def start_web_server_in_background():
       """在後台啟動Web服務器"""
       try:
           from web.server import run_server
           import threading

           # 從環境變量或配置讀取端口
           web_port = int(os.getenv('WEB_PORT', 5000))

           web_thread = threading.Thread(target=run_server, kwargs={
               'host': '0.0.0.0',
               'port': web_port,
               'debug': False
           }, daemon=True)
           web_thread.start()

           logger.info(f"Web服務器已在後台啟動: http://localhost:{web_port}")
           time.sleep(2)
       except Exception as e:
           logger.warning(f"啟動Web服務器失敗: {e}")
   ```

#### 4.2 在 `daemon_manager.py` 中設置 Web 端口環境變量

在 `_start_bot()` 方法中（line 550-670）：

```python
# 設置環境變量
env = os.environ.copy()
env.update(self.config.get("environment", {}))

# 添加 Web 端口環境變量
if "web_port" in self.config:
    env['WEB_PORT'] = str(self.config['web_port'])
```

---

### Phase 5：實例管理工具（0.5 天）

#### 5.1 創建實例管理模塊

創建 `core/instance_manager.py`：

```python
"""
實例管理器 - 統一管理多個交易機器人實例
"""
import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import psutil

class InstanceRegistry:
    """實例註冊表"""

    def __init__(self, registry_file: str = "logs/instances.json"):
        self.registry_file = Path(registry_file)
        self.registry_file.parent.mkdir(exist_ok=True)

    def register(self, instance_id: str, info: Dict) -> None:
        """註冊實例"""
        registry = self.load()
        registry[instance_id] = {
            **info,
            "registered_at": datetime.now().isoformat()
        }
        self.save(registry)

    def unregister(self, instance_id: str) -> None:
        """註銷實例"""
        registry = self.load()
        if instance_id in registry:
            del registry[instance_id]
            self.save(registry)

    def load(self) -> Dict:
        """加載註冊表"""
        if not self.registry_file.exists():
            return {}

        with open(self.registry_file, 'r') as f:
            return json.load(f)

    def save(self, registry: Dict) -> None:
        """保存註冊表"""
        with open(self.registry_file, 'w') as f:
            json.dump(registry, f, indent=2)

    def list_instances(self) -> List[Dict]:
        """列出所有實例"""
        registry = self.load()
        instances = []

        for instance_id, info in registry.items():
            # 檢查進程是否還在運行
            is_alive = False
            try:
                pid = info.get('pid')
                if pid and psutil.pid_exists(pid):
                    process = psutil.Process(pid)
                    if process.is_running():
                        is_alive = True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

            instances.append({
                "instance_id": instance_id,
                "is_alive": is_alive,
                **info
            })

        return instances

    def cleanup_dead_instances(self) -> int:
        """清理已死亡的實例記錄"""
        registry = self.load()
        dead_instances = []

        for instance_id, info in registry.items():
            pid = info.get('pid')
            if pid:
                try:
                    if not psutil.pid_exists(pid):
                        dead_instances.append(instance_id)
                except Exception:
                    dead_instances.append(instance_id)

        for instance_id in dead_instances:
            del registry[instance_id]

        if dead_instances:
            self.save(registry)

        return len(dead_instances)
```

#### 5.2 添加命令行工具

在 `cli/` 目錄下創建 `instance_cli.py`：

```python
"""
實例管理命令行工具
"""
import argparse
from core.instance_manager import InstanceRegistry
from tabulate import tabulate

def list_instances_cmd():
    """列出所有實例"""
    registry = InstanceRegistry()
    instances = registry.list_instances()

    if not instances:
        print("沒有運行中的實例")
        return

    # 格式化輸出
    headers = ["實例ID", "狀態", "PID", "Web端口", "配置文件", "啟動時間"]
    rows = []

    for inst in instances:
        status = "🟢 運行中" if inst['is_alive'] else "🔴 已停止"
        rows.append([
            inst['instance_id'],
            status,
            inst.get('pid', 'N/A'),
            inst.get('web_port', 'N/A'),
            inst.get('config_file', 'N/A'),
            inst.get('started_at', 'N/A')
        ])

    print(tabulate(rows, headers=headers, tablefmt='grid'))

def cleanup_instances_cmd():
    """清理已停止的實例記錄"""
    registry = InstanceRegistry()
    count = registry.cleanup_dead_instances()
    print(f"已清理 {count} 個已停止的實例記錄")

def main():
    parser = argparse.ArgumentParser(description='實例管理工具')
    subparsers = parser.add_subparsers(dest='command', help='命令')

    # list 命令
    subparsers.add_parser('list', help='列出所有實例')

    # cleanup 命令
    subparsers.add_parser('cleanup', help='清理已停止的實例記錄')

    args = parser.parse_args()

    if args.command == 'list':
        list_instances_cmd()
    elif args.command == 'cleanup':
        cleanup_instances_cmd()
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
```

---

## 4. 使用指南

### 4.1 創建多個實例配置

```bash
# 實例 1：Backpack SOL 永續網格
cat > config/active/bp_sol_01.json << 'EOF'
{
  "metadata": {
    "name": "Backpack SOL Grid Instance 1",
    "instance_id": "bp_sol_01",
    "exchange": "backpack",
    "symbol": "SOL_USDC_PERP",
    "market_type": "perp",
    "strategy": "perp_grid"
  },
  "daemon_config": {
    "python_path": ".venv/bin/python3",
    "script_path": "run.py",
    "working_dir": ".",
    "log_dir": "logs/bp_sol_01",
    "db_path": "database/bp_sol_01.db",
    "web_port": 5001,
    "bot_args": [
      "--exchange", "backpack",
      "--symbol", "SOL_USDC_PERP",
      "--strategy", "perp_grid",
      "--grid-lower", "140",
      "--grid-upper", "160",
      "--grid-num", "20",
      "--max-position", "10",
      "--duration", "86400",
      "--interval", "60"
    ]
  },
  "exchange_config": {
    "api_key": "${BACKPACK_KEY}",
    "secret_key": "${BACKPACK_SECRET}",
    "base_url": "https://api.backpack.work"
  },
  "strategy_config": {
    "grid_lower_price": 140,
    "grid_upper_price": 160,
    "grid_num": 20
  }
}
EOF

# 實例 2：Backpack ETH 永續網格
cat > config/active/bp_eth_02.json << 'EOF'
{
  "metadata": {
    "name": "Backpack ETH Grid Instance 2",
    "instance_id": "bp_eth_02",
    "exchange": "backpack",
    "symbol": "ETH_USDC_PERP",
    "market_type": "perp",
    "strategy": "perp_grid"
  },
  "daemon_config": {
    "python_path": ".venv/bin/python3",
    "script_path": "run.py",
    "working_dir": ".",
    "log_dir": "logs/bp_eth_02",
    "db_path": "database/bp_eth_02.db",
    "web_port": 5002,
    "bot_args": [
      "--exchange", "backpack",
      "--symbol", "ETH_USDC_PERP",
      "--strategy", "perp_grid",
      "--grid-lower", "2800",
      "--grid-upper", "3200",
      "--grid-num", "15",
      "--max-position", "5",
      "--duration", "86400",
      "--interval", "60"
    ]
  },
  "exchange_config": {
    "api_key": "${BACKPACK_KEY}",
    "secret_key": "${BACKPACK_SECRET}",
    "base_url": "https://api.backpack.work"
  },
  "strategy_config": {
    "grid_lower_price": 2800,
    "grid_upper_price": 3200,
    "grid_num": 15
  }
}
EOF
```

### 4.2 啟動實例

```bash
# 啟動實例 1
.venv/bin/python3 core/daemon_manager.py start --config config/active/bp_sol_01.json --daemon

# 啟動實例 2
.venv/bin/python3 core/daemon_manager.py start --config config/active/bp_eth_02.json --daemon

# 列出所有實例
.venv/bin/python3 core/daemon_manager.py list

# 或使用實例管理工具
.venv/bin/python3 cli/instance_cli.py list
```

### 4.3 管理實例

```bash
# 查看實例 1 狀態
.venv/bin/python3 core/daemon_manager.py status --config config/active/bp_sol_01.json

# 停止實例 1
.venv/bin/python3 core/daemon_manager.py stop --config config/active/bp_sol_01.json

# 重啟實例 2
.venv/bin/python3 core/daemon_manager.py restart --config config/active/bp_eth_02.json

# 清理已停止的實例記錄
.venv/bin/python3 cli/instance_cli.py cleanup
```

### 4.4 訪問 Web UI

```bash
# 實例 1 Web UI
http://localhost:5001

# 實例 2 Web UI
http://localhost:5002

# 健康檢查
curl http://localhost:5001/health
curl http://localhost:5002/health
```

### 4.5 熱調整網格範圍

```bash
# 調整實例 1 的網格範圍
curl -X POST http://localhost:5001/api/grid/adjust \
  -H "Content-Type: application/json" \
  -d '{
    "grid_upper_price": 165,
    "grid_lower_price": 135
  }'

# 調整實例 2 的網格範圍
curl -X POST http://localhost:5002/api/grid/adjust \
  -H "Content-Type: application/json" \
  -d '{
    "grid_upper_price": 3300,
    "grid_lower_price": 2700
  }'
```

---

## 5. 風險管理與最佳實踐

### 5.1 API 速率限制

**風險**：多個實例使用同一組 API Key 可能觸發速率限制。

**解決方案**：
1. 為不同實例使用不同的交易所子賬戶
2. 調整 `interval` 參數，避免同時查詢（錯開更新時間）
3. 監控 API 請求頻率

### 5.2 資源監控

**建議配置**：
- 每個實例約佔用 50-100 MB 內存
- 建議不超過 5-10 個實例（根據服務器配置）
- 使用 `htop` 或 `top` 監控資源使用

**監控腳本**：
```bash
#!/bin/bash
# monitor_instances.sh
watch -n 5 '
echo "=== 實例狀態 ==="
.venv/bin/python3 cli/instance_cli.py list
echo ""
echo "=== 系統資源 ==="
free -h
echo ""
echo "=== 磁盤空間 ==="
df -h | grep -E "(Filesystem|/dev/)"
'
```

### 5.3 錯誤隔離

**優點**：
- 一個實例崩潰不會影響其他實例
- 每個實例有獨立的日誌，易於排查

**建議**：
- 定期檢查日誌目錄大小
- 設置合理的 `log_retention_days`（建議 2-7 天）

### 5.4 安全注意事項

1. **環境變量保護**：
   - 確保 `.env` 文件不被提交到 Git
   - 使用 `chmod 600 .env` 限制權限

2. **API Key 隔離**：
   - 生產環境建議每個實例使用獨立的 API Key
   - 使用子賬戶限制權限

3. **Web UI 訪問控制**：
   - 生產環境建議使用 Nginx 反向代理
   - 添加 HTTP Basic Auth 或其他認證機制

---

## 6. 故障排查

### 6.1 常見問題

**Q1: 第二個實例啟動失敗，提示 "PID file already exists"**

**A:** 可能是第一個實例的 PID 文件與第二個實例衝突。檢查：
```bash
# 檢查是否使用了相同的 instance_id
cat config/active/instance1.json | grep instance_id
cat config/active/instance2.json | grep instance_id

# 清理殭屍 PID 文件
.venv/bin/python3 cli/instance_cli.py cleanup
```

**Q2: Web UI 無法訪問**

**A:** 檢查端口是否被佔用：
```bash
# 檢查端口
netstat -tlnp | grep 5001
netstat -tlnp | grep 5002

# 查看實例日誌
tail -f logs/bp_sol_01/2025-11-28/bot_stderr.log
```

**Q3: 數據庫鎖定錯誤**

**A:** 確認每個實例使用獨立的數據庫文件：
```bash
# 檢查配置
cat config/active/bp_sol_01.json | grep db_path
cat config/active/bp_eth_02.json | grep db_path

# 查看數據庫文件
ls -lh database/
```

### 6.2 日誌查看

```bash
# 查看守護進程日誌
tail -f logs/bp_sol_01/2025-11-28/daemon.log

# 查看策略運行日誌
tail -f logs/bp_sol_01/2025-11-28/bot_stdout.log
tail -f logs/bp_sol_01/2025-11-28/bot_stderr.log

# 查看所有實例的錯誤日誌
tail -f logs/*/2025-11-28/bot_stderr.log
```

---

## 7. 實施檢查清單

### Phase 1: 配置結構擴展
- [ ] 更新配置文件模板，添加 `instance_id`、`log_dir`、`db_path`、`web_port`
- [ ] 創建兩個測試配置文件（`bp_sol_01.json` 和 `bp_eth_02.json`）
- [ ] 驗證環境變量展開功能

### Phase 2: 守護進程改造
- [ ] 修改 `__init__` 方法，支持 `instance_id` 參數
- [ ] 實現實例註冊機制（`_register_instance`, `_unregister_instance`）
- [ ] 修改日誌路徑邏輯
- [ ] 修改 PID 文件路徑
- [ ] 添加 `list` 命令到 CLI
- [ ] 測試單實例啟動

### Phase 3: 數據庫隔離
- [ ] 檢查 `database/db.py`，確認支持動態路徑
- [ ] 修改策略初始化，傳遞正確的數據庫路徑

### Phase 4: Web 服務器改造
- [ ] 修改 `run_server()` 支持動態端口
- [ ] 在 `daemon_manager.py` 中設置 `WEB_PORT` 環境變量
- [ ] 測試不同端口啟動

### Phase 5: 實例管理工具
- [ ] 創建 `core/instance_manager.py`
- [ ] 創建 `cli/instance_cli.py`
- [ ] 測試 `list` 和 `cleanup` 命令

### Phase 6: 集成測試
- [ ] 同時啟動兩個實例
- [ ] 驗證 PID、日誌、數據庫隔離
- [ ] 驗證 Web UI 訪問
- [ ] 測試實例停止和重啟
- [ ] 測試網格熱調整功能
- [ ] 壓力測試（啟動 5 個實例）

---

## 8. 預期工作量與時間表

| 階段 | 工作量 | 優先級 | 依賴 |
|------|--------|--------|------|
| Phase 1: 配置結構擴展 | 0.5 天 | P0 | 無 |
| Phase 2: 守護進程改造 | 1 天 | P0 | Phase 1 |
| Phase 3: 數據庫隔離 | 0.5 天 | P0 | Phase 2 |
| Phase 4: Web 服務器改造 | 1 天 | P0 | Phase 2 |
| Phase 5: 實例管理工具 | 0.5 天 | P1 | Phase 2 |
| Phase 6: 集成測試 | 0.5 天 | P0 | All |

**總計：約 4 天**（假設全職開發，實際可能需要 1-2 週）

---

## 9. 後續改進建議

### 9.1 短期改進（1-2 週）

1. **統一 Web UI**（可選）
   - 創建一個主控制台，列出所有實例
   - 支持從單一界面切換和控制不同實例

2. **實例自動恢復**
   - 系統重啟後自動恢復之前運行的實例

3. **配置熱重載**
   - 修改配置文件後自動重啟實例

### 9.2 長期改進（1-2 個月）

1. **Docker 容器化**
   - 每個實例運行在獨立的 Docker 容器中
   - 使用 Docker Compose 管理多實例

2. **監控告警系統**
   - Prometheus + Grafana 監控
   - 異常情況自動告警（釘釘、郵件、Telegram）

3. **集中式日誌管理**
   - ELK Stack (Elasticsearch + Logstash + Kibana)
   - 統一查看和搜索所有實例日誌

4. **配置管理 UI**
   - Web 界面創建、編輯、管理配置文件
   - 配置版本控制和回滾

---

## 10. 總結與下一步

### ✅ 可行性評估

**結論：高度可行**

- 現有架構已具備 80% 的基礎設施
- 主要工作是資源隔離和實例管理
- 預計 4 天開發時間即可完成核心功能

### 🚀 建議的實施順序

1. **先完成 Phase 1-4**（3 天）：實現基本的多實例運行
2. **測試驗證**（0.5 天）：確保兩個實例可以穩定並發運行
3. **補充 Phase 5**（0.5 天）：添加管理工具
4. **生產部署**：根據實際需求調整配置

### 📋 下一步行動

**請確認以下事項，我將開始實施：**

1. ✅ 是否認可這個技術方案？
2. ✅ 是否需要調整某些設計細節？
3. ✅ 優先實施哪些 Phase？（建議先做 Phase 1-4）
4. ✅ 是否需要先進行原型驗證？

**準備就緒後，我將按照以下順序開始實施：**
1. 創建示例配置文件
2. 修改 `daemon_manager.py`
3. 測試雙實例啟動
4. 完善文檔和使用指南

---

**文檔版本**：2.0
**作者**：Claude Code
**最後更新**：2025-11-28
**審閱狀態**：待用戶確認

---

## 附錄：參考資料

- 原始需求：`multi_perp_grid_bot_analysis_20251127.md`（已刪除）
- 配置管理代碼：`core/config_manager.py`
- 守護進程代碼：`core/daemon_manager.py`
- 項目架構：`CLAUDE.md`
