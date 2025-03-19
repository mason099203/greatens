# 桂田集團訂位管理系統
?
## 專案概述
這是一個使用 Docker 容器化的餐廳訂位管理系統，使用 Python Flask 作為後端框架，採用 MySQL 資料庫。主要功能是管理餐廳訂位資料，支援多用戶訪問，並提供完整的數據分析功能。

## 主要檔案結構
1. **Docker 相關檔案**：
   - `Dockerfile`：基於 Python 3.9-slim，設定時區為台灣時區，安裝必要的 Python 套件。
   - `docker-compose.yml`：定義容器服務，將宿主機 logs 目錄映射到容器中，設定網路和端口。

2. **後端程式**：
   - `src/app.py`：主要的 Flask 應用程式，提供登入、訂位管理、報表生成等功能。
   - `src/.env`：環境變數配置，包含資料庫連線資訊、LINE Bot 設定和 OpenAI API 金鑰。

3. **主要功能模組**：
   - 使用者認證系統（登入/登出）
   - 訂位資料管理（新增/編輯/刪除）
   - Excel 檔案上傳與匯出
   - 統計報表與資料視覺化
   - LINE Bot 整合
   - 日誌記錄系統

## 技術細節
- **後端框架**：Flask 2.2.2
- **資料庫**：MySQL (透過 Flask-MySQLdb 和 mysql-connector-python)
- **前端**：HTML/CSS/JavaScript (儀表板和報表頁面)
- **API 整合**：LINE Bot API、OpenAI API
- **容器化**：Docker
- **部署**：使用 waitress 作為生產環境 WSGI 伺服器

## 特殊功能
1. **資料庫操作**：完整的 CRUD 操作，包含資料驗證和錯誤處理
2. **Excel 整合**：支援批量上傳訂位資料和匯出報表
3. **統計分析**：提供各種統計報表（訂位趨勢、區域分佈、人數分佈等）
4. **日誌系統**：使用 Python logging 模組實現每日輪換的日誌記錄

## 安全性
- 使用環境變數存儲敏感資訊
- 實作登入驗證系統
- 對使用者輸入進行資料驗證

## 部署指南

### 環境需求
- Docker 與 Docker Compose
- MySQL 資料庫

### 安裝步驟
1. 複製專案到本地：
   ```
   git clone https://github.com/your-repository/greatens_docker.git
   cd greatens_docker
   ```

2. 設定環境變數：
   - 複製 `src/.env.example` 到 `src/.env`（如果存在的話）
   - 編輯 `.env` 檔案，填入必要的環境變數

3. 啟動容器：
   ```
   docker-compose up -d
   ```

4. 訪問網頁：
   - 本地訪問：http://localhost:9001
   - 使用 ngrok 提供外部訪問：`./src/ngrok http 9001`

### 資料庫設定
系統需要一個 MySQL 資料庫，請確保在 `.env` 檔案中正確設定資料庫連線資訊。

## API 端點

### 使用者認證
- `/login` - 使用者登入
- `/logout` - 使用者登出

### 訂位管理
- `/dashboard` - 主控台頁面，顯示所有訂位資料
- `/add_booking` - 新增單筆訂位資料
- `/edit/<int:id>` - 編輯指定的訂位資料
- `/delete/<int:id>` - 刪除指定的訂位資料
- `/batch_delete` - 批量刪除訂位資料

### 檔案處理
- `/upload` - 上傳 Excel 檔案批量新增訂位資料
- `/export_data` - 匯出訂位資料為 Excel
- `/download_template` - 下載 Excel 範本

### 統計報表
- `/reports` - 統計報表頁面
- `/api/reports` - 獲取報表資料的 API
- `/table-stats` - 桌位統計報表頁面
- `/api/table-stats` - 獲取桌位統計數據的 API
- `/api/table-details/<table_number>` - 獲取特定桌號的詳細訂位記錄
- `/parking-stats` - 停車場統計報表頁面
- `/api/parking-stats` - 獲取停車場統計數據的 API
- `/api/parking-details/<parking_lot>` - 獲取特定停車場的詳細訂位記錄

### 搜尋功能
- `/search` - 根據姓名或公司名稱搜尋訂位資料

## 日誌記錄
系統會自動記錄各種操作和錯誤，日誌檔案存放在 `logs` 目錄中，使用每日輪換的方式保存。

## 注意事項
- 請確保敏感資訊（如 API 金鑰、資料庫密碼）不會被公開
- 定期備份資料庫資料
- 檢查 logs 目錄的磁碟空間使用情況，避免日誌檔案佔用過多空間

# Python 虛擬環境設置指南

## 環境需求
- Python 3.x
- pip (Python 套件管理器)

## 建立虛擬環境步驟

1. 以系統管理員身份開啟命令提示字元或 PowerShell

2. 切換到專案目錄
```bash
cd 專案目錄路徑
```

3. 建立虛擬環境
```bash
python -m venv .venv
```

4. 啟動虛擬環境
- Windows:
```bash
.\.venv\Scripts\activate
```

5. 安裝所需套件
```bash
pip install -r requirements.txt
```


## 注意事項
- 如果在建立虛擬環境時遇到權限問題，請確保使用系統管理員權限執行命令
- 建議在每次開始開發前都先啟動虛擬環境
- 如果需要安裝新的套件，請記得更新 requirements.txt
