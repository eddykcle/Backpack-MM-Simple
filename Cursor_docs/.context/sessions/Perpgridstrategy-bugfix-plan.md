PerpGridStrategy 日志和停止机制 Bug 修复计划
问题分析
问题 1: 配置文件参数未被正确读取 (关键根因)
症状: 配置文件设置 grid_upper_price: 3200，但实际使用的是 2994.8

根因: daemon_manager.py:193-209 的 _build_bot_args 方法键名不匹配

# daemon_manager.py 期望的键名
grid_params = ["grid-upper", "grid-lower", ...]  # 转换后: grid_upper, grid_lower

# 配置文件实际的键名
"grid_upper_price": 3200,  # 不匹配！
"grid_lower_price": 2800,  # 不匹配！
导致命令行参数 --grid-upper 和 --grid-lower 未被传递，策略使用自动价格计算。

问题 2: 策略边界触发后无法停止 (严重)
症状: 日志显示价格超出网格边界后执行了 emergency_close，但策略继续循环

根因: perp_grid_strategy.py 第1969行设置的是 self._stop_trading = True，但主循环 (market_maker.py 第2348行) 只检查 self._stop_flag:
# market_maker.py:2348
while time.time() - start_time < duration_seconds and not self._stop_flag:
问题 3: 多策略日志文件同时记录 (中等)
症状: 运行 perp_grid_strategy 时，market_maker.log 和 perp_market_maker.log 也有记录

根因: 模块级 logger 创建机制

market_maker.py:21 → logger = setup_logger("market_maker")
perp_market_maker.py:18 → logger = setup_logger("perp_market_maker")
perp_grid_strategy.py:18 → logger = setup_logger("perp_grid_strategy")
由于继承关系，父类代码（如 __init__、统计方法）使用父类的 logger 记录。

问题 3: 日志文件命名格式异常 (轻微)
症状: 文件名变成 perp_grid_strategy.log.2025-11-29

根因: CompressedRotatingFileHandler 的 time_based 模式在已有日期目录的路径上再次追加日期

---

修复方案
修复 1: 策略停止机制
修改 strategies/perp_grid_strategy.py 的 _handle_boundary_breach 方法：

# 同时设置 _stop_flag 确保主循环退出
self._stop_flag = True
self._stop_trading = True
修复 2: 日志文件命名
修改 core/log_manager.py 的 CompressedRotatingFileHandler.__init__，移除对已在日期目录中文件的二次日期追加：

if self.time_based:
    # 如果文件已在日期目录中，不再追加日期后缀
    parent_dir = Path(self.baseFilename).parent.name
    if not self._is_date_format(parent_dir):
        self.date_filename = f"{self.baseFilename}.{self.current_date.strftime('%Y-%m-%d')}"
        self.baseFilename = self.date_filename
修复 3: 日志隔离 (可选优化)
此为预期行为，父类代码使用父类 logger。如需统一，可：

在子类 __init__ 中传递 logger name 给父类
或修改父类使用 self.logger 实例属性而非模块 logger
---

涉及文件
| 文件 | 修改类型 |

|------|----------|

| strategies/perp_grid_strategy.py | 修复停止逻辑 (关键) |

| core/log_manager.py | 修复文件命名 |