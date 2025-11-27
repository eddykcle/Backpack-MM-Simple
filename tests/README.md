# 測試文檔

本目錄包含多配置管理系統的測試文件。

## 測試文件結構

```
tests/
├── README.md                    # 本文件
├── run_tests.py                # 測試運行腳本
├── test_config_manager.py       # 配置管理器測試
└── test_reports/              # 測試報告目錄（自動生成）
```

## 運行測試

### 方法1：使用測試運行腳本（推薦）

```bash
# 運行配置管理器測試
python tests/run_tests.py config

# 運行所有測試
python tests/run_tests.py all

# 生成測試報告
python tests/run_tests.py report
```

### 方法2：直接運行單個測試文件

```bash
# 運行配置管理器測試
python -m unittest tests.test_config_manager

# 運行所有測試
python -m unittest discover tests
```

### 方法3：使用 pytest（如果已安裝）

```bash
# 運行所有測試
pytest tests/

# 運行特定測試文件
pytest tests/test_config_manager.py

# 生成覆蓋率報告
pytest tests/ --cov=core --cov-report=html
```

## 測試覆蓋範圍

### 配置管理器測試 (test_config_manager.py)

- ✅ 目錄創建功能
- ✅ 配置保存和加載
- ✅ 配置驗證
- ✅ 環境變量展開
- ✅ 環境變量安全性檢查
- ✅ 配置備份和恢復
- ✅ 備份完整性檢查
- ✅ 從模板創建配置
- ✅ 配置列表和篩選
- ✅ 配置刪除
- ✅ 錯誤處理

## 測試報告

運行 `python tests/run_tests.py report` 後，測試報告將保存在 `test_reports/` 目錄中，包含：

- 標準輸出內容
- 錯誤輸出內容
- 測試結果總結
- 執行時間統計

## 持續集成

可以在 CI/CD 流程中集成測試：

```yaml
# GitHub Actions 示例
- name: Run Tests
  run: |
    python tests/run_tests.py all
    python tests/run_tests.py report
```

## 添加新測試

1. 在 `tests/` 目錄下創建新的測試文件，命名格式為 `test_*.py`
2. 繼承 `unittest.TestCase` 類
3. 編寫測試方法，方法名以 `test_` 開頭
4. 運行測試確保通過

示例：

```python
import unittest
from core.some_module import SomeClass

class TestSomeClass(unittest.TestCase):
    def setUp(self):
        """測試前準備"""
        self.obj = SomeClass()
    
    def test_some_method(self):
        """測試某個方法"""
        result = self.obj.some_method()
        self.assertEqual(result, expected_value)
```

## 調試測試

如果測試失敗，可以使用以下方法調試：

1. 增加輸出詳細程度：
   ```bash
   python -m unittest tests.test_config_manager -v
   ```

2. 在測試中添加調試輸出：
   ```python
   def test_something(self):
       # 調試輸出
       print(f"Debug: {some_variable}")
       self.assertEqual(result, expected)
   ```

3. 使用 IDE 的調試功能設置斷點

## 最佳實踐

1. **測試命名**：使用描述性的測試名稱，清楚說明測試內容
2. **測試隔離**：每個測試應該獨立，不依賴其他測試的狀態
3. **清理資源**：在 `tearDown()` 方法中清理測試創建的資源
4. **覆蓋邊界**：測試正常情況和異常情況
5. **模擬外部依賴**：使用 mock 對象隔離外部依賴

## 常見問題

### Q: 測試失敗提示 "ModuleNotFoundError"
A: 確保在項目根目錄運行測試，或者設置 PYTHONPATH 環境變量

### Q: 測試運行很慢
A: 可以使用 `-k` 參數運行特定測試：
   ```bash
   python -m unittest tests.test_config_manager.TestConfigManager.test_save_and_load_config
   ```

### Q: 如何測試私有方法？
A: 可以通過 `obj._private_method()` 方式訪問，但建議測試公共接口