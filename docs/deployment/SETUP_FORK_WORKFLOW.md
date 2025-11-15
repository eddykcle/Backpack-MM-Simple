# Git Fork 工作流程設置指南

## 目標
- 保留你對項目的修改（健康檢查功能）
- 能夠持續從原始倉庫拉取更新
- 維護你自己的版本控制

## 步驟 1: Fork 原始倉庫

1. 登錄你的 GitHub 賬戶
2. 訪問原始倉庫：https://github.com/yanowo/Backpack-MM-Simple
3. 點擊右上角的 "Fork" 按鈕
4. 選擇你的賬戶作為 fork 目標
5. 等待 fork 完成

## 步驟 2: 添加你的 Fork 作為新遠程

在你的本地項目目錄中執行：

```bash
# 添加你的 fork 作為新的遠程倉庫
git remote add myfork https://github.com/你的用戶名/Backpack-MM-Simple.git

# 驗證遠程設置
git remote -v
```

## 步驟 3: 提交你的修改

```bash
# 添加所有修改的文件
git add .

# 提交你的修改
git commit -m "添加健康檢查功能供 Uptime Kuma 監聽

- 修改 web/server.py 添加健康檢查端點
- 修改 run.py 在 terminal 執行時自動啟動 Web 服務器
- 添加健康檢查端點 /health 和 /health/detailed"
```

## 步驟 4: 推送到你的 Fork

```bash
# 推送到你的 fork
git push myfork main
```

## 步驟 5: 設置上游倉庫同步

```bash
# 添加原始倉庫作為上游
git remote add upstream https://github.com/yanowo/Backpack-MM-Simple.git

# 驗證設置
git remote -v
```

你應該看到：
- `origin` -> 原始倉庫
- `myfork` -> 你的 fork
- `upstream` -> 原始倉庫（用於同步更新）

## 工作流程

### 日常開發
```bash
# 工作並提交到你的 fork
git add .
git commit -m "你的修改描述"
git push myfork main
```

### 同步上游更新
```bash
# 1. 獲取上游更新
git fetch upstream

# 2. 切換到主分支
git checkout main

# 3. 合併上游更新
git merge upstream/main

# 4. 解決可能的衝突（如果有）
# 5. 推送更新到你的 fork
git push myfork main
```

### 高級工作流程（使用 rebase 保持乾淨歷史）
```bash
# 1. 獲取上游更新
git fetch upstream

# 2. 創建並切換到新分支進行開發
git checkout -b feature/your-feature

# 3. 工作並提交
git add .
git commit -m "你的功能"

# 4. 切換回主分支
git checkout main

# 5. 重新基於上游更新
git rebase upstream/main

# 6. 合併你的功能分支
git merge feature/your-feature

# 7. 推送到你的 fork
git push myfork main
```

## 衝突解決

當上游有更新且與你的修改衝突時：

1. **手動解決衝突**：
   ```bash
   git merge upstream/main
   # 解決衝突文件
   git add .
   git commit -m "合併上游更新並解決衝突"
   ```

2. **使用工具輔助**：
   - VS Code 有內建的衝突解決工具
   - 或使用 `git mergetool`

## 最佳實踐

### 1. 定期同步
建議每週或每月同步一次上游更新，避免累積太多衝突。

### 2. 小步提交
保持提交小而專注，便於管理和回滾。

### 3. 文檔記錄
在 README 或單獨的文檔中記錄你的修改，便於追蹤。

### 4. 分支策略
對於大型修改，使用功能分支：
```bash
git checkout -b feature/uptime-kuma-integration
# 工作...
git push myfork feature/uptime-kuma-integration
```

## 常見問題

### Q: 如何查看哪些文件有衝突？
A: ```bash
git status
# 或
git diff --name-only --diff-filter=U
```

### Q: 如何放棄合併？
A: ```bash
git merge --abort
```

### Q: 如何只獲取特定文件的上游版本？
A: ```bash
git checkout upstream/main -- path/to/file
```

## 當前項目狀態

你的當前修改包括：
- ✅ 添加了健康檢查端點 (`/health`)
- ✅ 修改了 `run.py` 自動啟動 Web 服務器
- ✅ 添加了 Uptime Kuma 設置文檔
- ✅ 創建了測試腳本

這些修改已經可以提交並推送到你的 fork 了！

## 下一步

1. 按照上述步驟 fork 原始倉庫
2. 設置你的 fork 作為遠程
3. 提交並推送你的修改
4. 之後就可以輕鬆同步上游更新了！

這樣你就能：
- ✅ 保留你的健康檢查功能
- ✅ 持續獲得原始項目的更新
- ✅ 維護你自己的版本控制
