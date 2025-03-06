# 1) 使用 python 3.9 slim 版本為基底
FROM python:3.9-slim

# 3) 安裝必要套件 (libaio1 供 Oracle Instant Client 使用; wget、unzip 來下載與解壓縮)
RUN apt-get update && \
    apt-get install -y libaio1 wget unzip \
    pkg-config \
    default-libmysqlclient-dev \
    build-essential \
    python3-dev && \
    rm -rf /var/lib/apt/lists/*

# 安裝必要套件 + tzdata
RUN apt-get update && \
apt-get install -y tzdata && \
rm -rf /var/lib/apt/lists/*

# 設定 TZ 環境變數 (例如台灣時區)
ENV TZ=Asia/Taipei

# 將容器時間鏈結到對應時區
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && \
    echo $TZ > /etc/timezone
    
# 5) 設定工作目錄
WORKDIR /app

# 6) 複製 requirements.txt 並安裝 Python 套件
COPY requirements.txt /app/
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 7) 複製專案程式碼到容器 (請調整路徑對應您的檔案結構)
COPY src/ /app/

# 8) 對外曝光 Flask 預設埠號 (如有需要)
EXPOSE 9001

# 9) 容器啟動後的預設執行指令
CMD ["python", "app.py"]
