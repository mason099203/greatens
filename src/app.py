from flask import Flask, send_from_directory, send_file, render_template, request, redirect, url_for, session, jsonify
from flask_cors import CORS
import os
from dotenv import load_dotenv
import mysql.connector
from functools import wraps
import time
import pandas as pd
from io import BytesIO
from datetime import datetime
from werkzeug.utils import secure_filename
from line_routes import init_line_routes
import logging
from logging.handlers import TimedRotatingFileHandler
import pathlib

# 載入 .env 變數
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

def setup_logger():
    """設定日誌"""
    # 創建 logs 目錄
    log_dir = pathlib.Path('logs')
    log_dir.mkdir(exist_ok=True)
    
    # 設定日誌檔案名稱格式
    log_file = log_dir / 'app.log'
    
    # 設定日誌格式
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 獲取 root logger
    logger = logging.getLogger()
    
    # 如果 logger 已經有 handlers，則不需要再次設置
    if logger.handlers:
        return logger
    
    # 設定 TimedRotatingFileHandler
    file_handler = TimedRotatingFileHandler(
        filename=log_file,
        when='midnight',  # 每天午夜切換新檔案
        interval=1,       # 間隔為1天
        backupCount=30,   # 保留30天的日誌
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.suffix = '%Y%m%d.log'  # 設定檔案後綴格式
    
    # 設定 console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # 設定 root logger
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# 初始化日誌
logger = setup_logger()

app = Flask(__name__)
CORS(app)

# 初始化 LINE 路由
# init_line_routes(app)

FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
FLASK_PORT = os.getenv("FLASK_PORT", "")
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}

# 設定 Session 密鑰
app.secret_key = 'your_secret_key_here'  # 請更換為安全的密鑰

# MySQL 設定
MYSQL_HOST = os.getenv('MYSQL_HOST', 'localhost')
MYSQL_USER = os.getenv('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', '')
MYSQL_DB = os.getenv('MYSQL_DB', 'greatenDB')
MYSQL_PORT = int(os.getenv('MYSQL_PORT', 3306))
MYSQL_CONNECT_TIMEOUT = int(os.getenv('MYSQL_CONNECT_TIMEOUT', 120))

def allowed_file(filename):
    """
    檢查檔案類型是否允許
    """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def login_required(f):
    """
    登入驗證裝飾器
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_db_connection(max_retries=5, retry_delay=5):
    """獲取資料庫連線，包含重試機制"""
    for attempt in range(max_retries):
        try:
            logger.info(f'嘗試連接資料庫 (第 {attempt + 1} 次)')
            logger.info(f'連線設定: HOST={MYSQL_HOST}, PORT={MYSQL_PORT}, DB={MYSQL_DB}')
            
            connection = mysql.connector.connect(
                host=MYSQL_HOST,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                database=MYSQL_DB,
                port=MYSQL_PORT,
                connect_timeout=MYSQL_CONNECT_TIMEOUT
            )

            # 測試連線
            cursor = connection.cursor()
            cursor.execute('SELECT 1')
            cursor.fetchall()  # 讀取測試查詢的結果
            cursor.close()     # 關閉測試用的游標
            
            logger.info('資料庫連線成功')
            return connection
            
        except Exception as e:
            logger.error(f'資料庫連線嘗試 {attempt + 1}/{max_retries} 失敗')
            logger.error(f'錯誤類型: {type(e).__name__}')
            logger.error(f'錯誤訊息: {str(e)}')
            logger.error(f'錯誤詳情: {repr(e)}')
            
            if attempt < max_retries - 1:
                logger.info(f'等待 {retry_delay} 秒後重試...')
                time.sleep(retry_delay)
            else:
                logger.error('已達最大重試次數，放棄連線')
                raise

# 設定圖片上傳資料夾
app.config['UPLOAD_FOLDER'] = 'images'
# 添加 Excel 備份資料夾設定
app.config['EXCEL_BACKUP_FOLDER'] = 'uploads'

# 確保圖片和備份資料夾存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['EXCEL_BACKUP_FOLDER'], exist_ok=True)

@app.route('/')
def index():
    """
    提供首頁
    """
    try:
        # 記錄首頁請求
                # 獲取用戶端 IP
        client_ip = request.remote_addr
        if request.headers.get('X-Forwarded-For'):
            client_ip = request.headers.get('X-Forwarded-For').split(',')[0]
        logger.info(f'IP: {client_ip} ,收到首頁請求')
        return send_file('index.html')
    except Exception as e:
        logger.error(f'提供首頁時發生錯誤: {str(e)}')
        return '頁面載入失敗', 500

@app.route('/edit/<int:id>', methods=['POST'])
@login_required
def edit_item(id):
    """
    編輯指定的訂位資料
    """
    try:
        data = request.json
        
        # 資料驗證
        if not data.get('contact_name') or len(data['contact_name']) < 2:
            return jsonify({'success': False, 'message': '姓名不可為空且至少需要2個字'}), 400
        
        if not data.get('company_name') or len(data['company_name']) < 2:
            return jsonify({'success': False, 'message': '公司名稱不可為空且至少需要2個字'}), 400
                    
        try:
            people_count = int(data.get('people_count', 0))
            if people_count < 1 or people_count > 999:
                return jsonify({'success': False, 'message': '人數必須在1-999之間'}), 400
        except ValueError:
            return jsonify({'success': False, 'message': '人數必須為有效數字'}), 400
            
        if not data.get('table_layout') or len(data['table_layout']) < 1:
            return jsonify({'success': False, 'message': '區域不可為空且至少需要1個字'}), 400
        
        if not data.get('table_layout_detail') or len(data['table_layout_detail']) < 1:
            return jsonify({'success': False, 'message': '桌位圖不可為空且至少需要1個字'}), 400
        
        if data.get('parking') and len(data['parking']) > 100:
            return jsonify({'success': False, 'message': '停車場不可超過100字'}), 400
        
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("""
            UPDATE booking_data 
            SET contact_name = %s,
                company_name = %s,                
                people_count = %s,
                table_layout = %s,
                table_layout_detail = %s,
                parking = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (
            data['contact_name'],
            data['company_name'],            
            people_count,
            data['table_layout'],
            data['table_layout_detail'],
            data.get('parking', ''),
            id
        ))
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True, 
            'message': '更新成功',
            'data': {
                'id': id,
                'contact_name': data['contact_name'],
                'company_name': data['company_name'],                
                'people_count': people_count,
                'table_layout': data['table_layout'],
                'table_layout_detail': data['table_layout_detail'],
                'parking': data.get('parking', '')
            }
        })
    except Exception as e:
        logger.error(f'更新資料時發生錯誤: {str(e)}')
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/images/<path:filename>')
def serve_image(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/style.css')
def serve_css():
    return send_file('style.css')

@app.route('/json/<path:filename>')
def serve_src(filename):
    return send_from_directory("json", filename)




@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # 獲取用戶端 IP
        client_ip = request.remote_addr
        if request.headers.get('X-Forwarded-For'):
            client_ip = request.headers.get('X-Forwarded-For').split(',')[0]
        
        logger.info(f'使用者嘗試登入: {username}, IP: {client_ip}')
        
        try:
            logger.info('開始建立資料庫連線')
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)
            
            logger.info('執行使用者查詢')
            cursor.execute("""
                SELECT id, username, password, full_name 
                FROM users 
                WHERE username = %s AND is_active = TRUE
            """, (username,))
            
            user = cursor.fetchone()
            cursor.close()
            connection.close()
            
            logger.info(f'查詢結果: {"成功" if user else "未找到使用者"}')
            
            if user and user['password'] == password:
                logger.info(f'使用者 {username} 登入成功 (IP: {client_ip})')
                session['logged_in'] = True
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['full_name'] = user['full_name']
                return redirect(url_for('dashboard'))
            else:
                logger.warning(f'使用者 {username} 登入失敗: 帳號或密碼錯誤 (IP: {client_ip})')
                error = '帳號或密碼錯誤'
                
        except Exception as e:
            logger.error('登入過程中發生錯誤')
            logger.error(f'錯誤類型: {type(e).__name__}')
            logger.error(f'錯誤訊息: {str(e)}')
            logger.error(f'錯誤詳情: {repr(e)}')
            logger.error(f'使用者資料: {user if "user" in locals() else "未取得"}')
            logger.error(f'用戶端 IP: {client_ip}')
            error = '系統連線異常，請稍後再試'
    
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    """
    處理登出請求
    @route: /logout
    @method: GET
    @return: 重導至登入頁面
    """
    session.clear()
    return redirect(url_for('login'))

@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    """
    處理檔案上傳
    """
    connection = None
    cursor = None
    filepath = None
    
    if 'file' not in request.files:
        return '沒有檔案', 400
    
    file = request.files['file']
    if file.filename == '':
        return '沒有選擇檔案', 400
    
    if file and allowed_file(file.filename):
        # 生成臨時檔案名稱
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        try:
            # 讀取 Excel 文件
            df = pd.read_excel(filepath)
            
            # 檢查必要欄位是否存在
            required_columns = ['姓名', '公司名稱', '人數', '區域', '桌位圖', '停車場']
            if not all(col in df.columns for col in required_columns):
                return 'Excel 檔案格式不正確，請使用正確的範本', 400
            
            # 資料預處理
            df['人數'] = pd.to_numeric(df['人數'], errors='coerce')
            df = df.fillna({'停車場': ''})  # 將停車場的 NaN 值替換為空字符串
            
            # 資料驗證
            if df['人數'].isnull().any():
                return '人數欄位包含無效數據', 400
            
            if (df['人數'] <= 0).any() or (df['人數'] > 999).any():
                return '人數必須在1-999之間', 400
            
            if df['姓名'].isnull().any() or df['公司名稱'].isnull().any() or df['區域'].isnull().any() or df['桌位圖'].isnull().any():
                return '除了停車場以外的欄位不能為空', 400
            
            # 建立資料庫連接
            connection = get_db_connection()
            cursor = connection.cursor()
            
            # 插入資料
            success_count = 0
            error_count = 0
            
            for _, row in df.iterrows():
                try:
                    sql = """
                        INSERT INTO booking_data 
                        (contact_name, company_name, people_count, table_layout, table_layout_detail, parking)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """
                    cursor.execute(sql, (
                        str(row['姓名']).strip(),
                        str(row['公司名稱']).strip(),
                        int(row['人數']),
                        str(row['區域']).strip(),
                        str(row['桌位圖']).strip(),
                        str(row['停車場']).strip()
                    ))
                    success_count += 1
                except Exception as row_error:
                    error_count += 1
                    logger.error(f'插入資料時發生錯誤: {str(row_error)}, 資料: {row.to_dict()}')
            
            if success_count > 0:
                connection.commit()
                
                # 備份 Excel 檔案
                backup_filename = f"ExcelImport_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
                backup_filepath = os.path.join(app.config['EXCEL_BACKUP_FOLDER'], backup_filename)
                
                # 複製檔案到備份資料夾
                import shutil
                shutil.copy2(filepath, backup_filepath)
                logger.info(f'Excel 檔案已備份至: {backup_filepath}')
                
                return f'檔案上傳成功，成功插入 {success_count} 筆資料' + (f'，{error_count} 筆資料失敗' if error_count > 0 else ''), 200
            else:
                return '沒有成功插入任何資料', 400
                
        except Exception as e:
            logger.error(f'處理檔案時發生錯誤: {str(e)}')
            return f'處理檔案時發生錯誤: {str(e)}', 500
            
        finally:
            # 清理資源
            if cursor:
                cursor.close()
            if connection:
                connection.close()
            if filepath and os.path.exists(filepath):
                os.remove(filepath)  # 刪除臨時檔案
    
    return '不支援的檔案類型', 400

@app.route('/export_data', methods=['GET'])
@login_required
def export_data():
    """
    匯出訂位資料為 Excel
    """
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # 查詢所需欄位
        cursor.execute("""
            SELECT 
                contact_name as '姓名',
                company_name as '公司名稱',
                people_count as '人數',
                table_layout as '區域',
                table_layout_detail as '桌位圖',
                parking as '停車場'
            FROM booking_data
            ORDER BY created_at DESC
        """)
        
        # 獲取資料
        data = cursor.fetchall()
        cursor.close()
        connection.close()
        
        # 轉換為 DataFrame
        columns = ['姓名', '公司名稱', '人數', '區域', '桌位圖', '停車場']
        df = pd.DataFrame(data, columns=columns)
        
        # 創建 Excel 檔案
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, 
                       sheet_name='訂位資料',
                       index=False)
        
        output.seek(0)
        
        # 設定檔案名稱（包含當前日期）
        filename = f'訂位資料_{datetime.now().strftime("%Y%m%d")}.xlsx'
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        logger.error('匯出資料時發生錯誤')
        logger.error(f'錯誤類型: {type(e).__name__}')
        logger.error(f'錯誤訊息: {str(e)}')
        return jsonify({'error': '匯出資料時發生錯誤'}), 500


@app.route('/delete/<int:id>', methods=['DELETE'])
@login_required
def delete_item(id):
    """
    刪除指定的訂位資料
    """
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("DELETE FROM booking_data WHERE id = %s", (id,))
        connection.commit()
        cursor.close()
        connection.close()
        return '刪除成功', 200
    except Exception as e:
        logger.error(f'刪除資料時發生錯誤: {str(e)}')
        return '刪除失敗', 500


@app.route('/download_template')
@login_required
def download_template():
    """
    下載 Excel 範本
    """
    try:
        return send_file('templates/greatenData.xlsx',
                        as_attachment=True,
                        download_name='greatenData.xlsx')
    except Exception as e:
        logger.error(f'下載範本時發生錯誤: {str(e)}')
        return '範本檔案不存在，請聯繫系統管理員', 500

@app.route('/add_booking', methods=['POST'])
@login_required
def add_booking():
    """
    新增單筆訂位資料
    """
    try:
        data = request.json
        logger.info(f'新增訂位資料: {data}')
        
        # 資料驗證
        if not data.get('contact_name') or len(data['contact_name']) < 2:
            return jsonify({'success': False, 'message': '姓名不可為空且至少需要2個字'}), 400
        
        if not data.get('company_name') or len(data['company_name']) < 2:
            return jsonify({'success': False, 'message': '公司名稱不可為空且至少需要2個字'}), 400     
        
        try:
            people_count = int(data.get('people_count', 0))
            if people_count < 1 or people_count > 999:
                return jsonify({'success': False, 'message': '人數必須在1-999之間'}), 400
        except ValueError:
            return jsonify({'success': False, 'message': '人數必須為有效數字'}), 400
            
        if not data.get('table_layout') or len(data['table_layout']) < 1:
            return jsonify({'success': False, 'message': '區域不可為空且至少需要12個字'}), 400
        
        if not data.get('table_layout_detail') or len(data['table_layout_detail']) < 1:
            return jsonify({'success': False, 'message': '桌位圖不可為空且至少需要1個字'}), 400
            
        if data.get('parking') and len(data['parking']) > 100:
            return jsonify({'success': False, 'message': '停車需求不可超過100字'}), 400
        
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            INSERT INTO booking_data 
            (contact_name, company_name, people_count, table_layout, table_layout_detail, parking)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            data['contact_name'],
            data['company_name'],
            people_count,
            data['table_layout'],
            data['table_layout_detail'],
            data.get('parking', '')
        ))
        connection.commit()
        cursor.close()
        connection.close()
        
        logger.info(f'訂位資料新增成功: {data}')
        return jsonify({
            'success': True,
            'message': '新增成功'
        })
    except Exception as e:
        logger.error(f'新增訂位資料時發生錯誤: {str(e)}')
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/batch_delete', methods=['POST'])
@login_required
def batch_delete():
    """
    批量刪除訂位資料
    """
    try:
        data = request.json
        ids = data.get('ids', [])

        if not ids:
            return jsonify({'success': False, 'message': '未選擇要刪除的資料'}), 400

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # 動態生成 %s 參數
        format_strings = ','.join(['%s'] * len(ids))
        query = f"DELETE FROM booking_data WHERE id IN ({format_strings})"
        
        # 執行 SQL
        cursor.execute(query, tuple(ids))
        connection.commit()

        deleted_count = cursor.rowcount  # 獲取刪除的行數
        cursor.close()
        connection.close()

        return jsonify({
            'success': True,
            'message': f'成功刪除 {deleted_count} 筆資料'
        })

    except Exception as e:
        logger.error(f'批量刪除資料時發生錯誤: {str(e)}')
        return jsonify({'success': False, 'message': str(e)}), 500



@app.route('/api/reports')
@login_required
def get_reports_data():
    """
    獲取報表資料的 API
    """
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        logger.info(f'報表查詢參數: start_date={start_date}, end_date={end_date}')
        
        # 使用統一的資料庫連接函數
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # 添加資料驗證
        cursor.execute("SELECT COUNT(*) as count FROM booking_data")
        total_count = cursor.fetchone()['count']
        
        if total_count == 0:
            logger.warning('資料庫中沒有資料')
            return jsonify({
                'summary': {
                    'total_bookings': 0,
                    'total_people': 0,
                    'parking_rate': 0,
                    'avg_daily_bookings': 0
                },
                'area_stats': [],
                'daily_stats': {'dates': [], 'counts': []},
                'people_distribution': {'ranges': [], 'counts': []},
                'parking_analysis': {'lots': [], 'counts': []},
                'company_analysis': {'names': [], 'bookings': [], 'people': []}
            })
        
        # 基本統計資料
        cursor.execute("""
            SELECT 
                COUNT(*) as total_bookings,
                COALESCE(CAST(SUM(people_count) AS SIGNED), 0) as total_people,
                COALESCE(ROUND(COUNT(CASE WHEN parking != '' AND parking IS NOT NULL THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0), 2), 0) as parking_rate,
                COALESCE(ROUND(COUNT(*) * 1.0 / NULLIF(COUNT(DISTINCT DATE(created_at)), 0), 2), 0) as avg_daily_bookings
            FROM booking_data
            WHERE DATE(created_at) BETWEEN DATE(%s) AND DATE(%s)
        """, (start_date, end_date))
        
        summary = cursor.fetchone()
        logger.info(f'摘要統計結果: {summary}')
        
        # 區域分布
        cursor.execute("""
            SELECT 
                COALESCE(table_layout, '未指定') as area,
                COUNT(*) as count,
                COALESCE(CAST(SUM(people_count) AS SIGNED), 0) as total_people
            FROM booking_data
            WHERE DATE(created_at) BETWEEN DATE(%s) AND DATE(%s)
            GROUP BY table_layout
            ORDER BY count DESC
        """, (start_date, end_date))
        
        area_stats = cursor.fetchall()
        
        # 每日訂位趨勢
        cursor.execute("""
            WITH RECURSIVE dates AS (
                SELECT DATE(%s) as date
                UNION ALL
                SELECT date + INTERVAL 1 DAY
                FROM dates
                WHERE date < DATE(%s)
            )
            SELECT 
                dates.date,
                COALESCE(COUNT(b.id), 0) as count
            FROM dates
            LEFT JOIN booking_data b ON DATE(b.created_at) = dates.date
            GROUP BY dates.date
            ORDER BY dates.date
        """, (start_date, end_date))
        
        daily_stats = cursor.fetchall()
        daily_data = {
            'dates': [item['date'].strftime('%Y-%m-%d') for item in daily_stats],
            'counts': [item['count'] for item in daily_stats]
        }
        
        # 人數分布統計
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN people_count <= 10 THEN '1-10人'
                    WHEN people_count <= 20 THEN '11-20人'
                    WHEN people_count <= 30 THEN '21-30人'
                    ELSE '30人以上'
                END as people_range,
                COUNT(*) as count
            FROM booking_data
            WHERE DATE(created_at) BETWEEN DATE(%s) AND DATE(%s)
            GROUP BY 
                CASE 
                    WHEN people_count <= 10 THEN '1-10人'
                    WHEN people_count <= 20 THEN '11-20人'
                    WHEN people_count <= 30 THEN '21-30人'
                    ELSE '30人以上'
                END
            ORDER BY 
                CASE people_range
                    WHEN '1-10人' THEN 1
                    WHEN '11-20人' THEN 2
                    WHEN '21-30人' THEN 3
                    ELSE 4
                END
        """, (start_date, end_date))
        
        people_dist = cursor.fetchall()
        people_distribution = {
            'ranges': [item['people_range'] for item in people_dist],
            'counts': [item['count'] for item in people_dist]
        }
        
        # 停車場分析
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN parking = '' OR parking IS NULL THEN '未指定'
                    ELSE parking 
                END as parking_lot,
                COUNT(*) as count
            FROM booking_data
            WHERE DATE(created_at) BETWEEN DATE(%s) AND DATE(%s)
            GROUP BY 
                CASE 
                    WHEN parking = '' OR parking IS NULL THEN '未指定'
                    ELSE parking 
                END
            ORDER BY 
                CASE 
                    WHEN parking_lot = '未指定' THEN 'Z'
                    ELSE parking_lot 
                END
        """, (start_date, end_date))
        
        parking_stats = cursor.fetchall()
        parking_analysis = {
            'lots': [item['parking_lot'] for item in parking_stats],
            'counts': [item['count'] for item in parking_stats]
        }
        
        # 公司分析
        cursor.execute("""
            SELECT 
                company_name,
                COUNT(*) as booking_count,
                CAST(SUM(people_count) AS SIGNED) as total_people
            FROM booking_data
            WHERE DATE(created_at) BETWEEN DATE(%s) AND DATE(%s)
                AND company_name IS NOT NULL 
                AND company_name != ''
            GROUP BY company_name
            ORDER BY total_people DESC
            LIMIT 10
        """, (start_date, end_date))
        
        company_stats = cursor.fetchall()
        company_analysis = {
            'names': [item['company_name'] for item in company_stats],
            'bookings': [item['booking_count'] for item in company_stats],
            'people': [item['total_people'] for item in company_stats]
        }
        
        cursor.close()
        connection.close()
        
        # 設置回應標頭，防止緩存
        response = jsonify({
            'summary': summary,
            'area_stats': area_stats,
            'daily_stats': daily_data,
            'people_distribution': people_distribution,
            'parking_analysis': parking_analysis,
            'company_analysis': company_analysis
        })
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
        
    except Exception as e:
        logger.error('獲取報表資料時發生錯誤')
        logger.error(f'錯誤類型: {type(e).__name__}')
        logger.error(f'錯誤訊息: {str(e)}')
        logger.error(f'錯誤詳情: {repr(e)}')
        logger.error(f'查詢參數: start_date={start_date}, end_date={end_date}')
        return jsonify({'error': str(e)}), 500


@app.route('/dashboard')
@login_required
def dashboard():
    """
    主控台頁面 - 顯示所有訂位資料
    """
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT 
                id,
                contact_name,
                company_name,
                CAST(people_count AS SIGNED) as people_count,
                table_layout,
                table_layout_detail,
                parking,
                created_at
            FROM booking_data 
            ORDER BY created_at DESC
        """)
        data = cursor.fetchall()
        cursor.close()
        connection.close()
        
        logger.info(f'成功讀取訂位資料，共 {len(data)} 筆記錄')
        return render_template('dashboard.html', data=data)
    except Exception as e:
        logger.error('讀取訂位資料時發生錯誤')
        logger.error(f'錯誤類型: {type(e).__name__}')
        logger.error(f'錯誤訊息: {str(e)}')
        logger.error(f'錯誤詳情: {repr(e)}')
        return '讀取資料時發生錯誤，請稍後再試', 500

@app.route('/reports')
@login_required
def reports():
    """
    統計報表頁面
    """
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # 獲取基本統計資料
        cursor.execute("""
            SELECT 
                COUNT(*) as total_bookings,
                SUM(people_count) as total_people,
                COUNT(CASE WHEN parking != '' THEN 1 END) * 100.0 / COUNT(*) as parking_rate,
                COUNT(*) * 1.0 / COUNT(DISTINCT DATE(created_at)) as avg_daily_bookings
            FROM booking_data
        """)
        # 獲取列名
        columns = [desc[0] for desc in cursor.description]
        # 轉換為字典
        stats = dict(zip(columns, cursor.fetchone()))
        
        cursor.close()
        return render_template('reports.html', stats=stats)
    except Exception as e:
        logger.error(f'獲取統計資料時發生錯誤: {str(e)}')
        return '獲取統計資料時發生錯誤，請稍後再試', 500



@app.route("/search", methods=["GET"])
def search():
    contact_name = request.args.get("contact_name", "").strip()
    client_ip = request.remote_addr
    if request.headers.get('X-Forwarded-For'):
        client_ip = request.headers.get('X-Forwarded-For').split(',')[0]
    
    logger.info(f'使用者search, IP: {client_ip}')

    if not contact_name:
        return jsonify({"error": "請提供 contact_name 參數"}), 400

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # SQL 查詢，根據 contact_name 搜尋
    query = """
        SELECT 
            id,
            contact_name,
            company_name,
            CAST(people_count AS SIGNED) AS people_count,
            table_layout,
            table_layout_detail,
            parking,
            created_at
        FROM booking_data 
        WHERE contact_name = %s 
        OR company_name LIKE %s 
        ORDER BY created_at DESC;
    """
    cursor.execute(query, (contact_name, '%' + contact_name + '%'))
    logger.info(f'IP: {client_ip}查詢: {contact_name}')

    data = cursor.fetchall()

    cursor.close()
    connection.close()

    return jsonify(data)

@app.route('/table-stats')
@login_required
def table_stats():
    """
    桌位統計報表頁面
    """
    return render_template('table_stats.html')

@app.route('/api/table-stats')
@login_required
def get_table_stats():
    """
    獲取桌位統計數據的 API
    """
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # 獲取每個桌號的統計數據
        cursor.execute("""
            SELECT 
                table_layout as area,
                table_layout_detail,
                COUNT(*) as booking_count,
                COALESCE(CAST(SUM(people_count) AS SIGNED), 0) as total_people
            FROM booking_data
            WHERE table_layout_detail IS NOT NULL AND table_layout_detail != ''
            GROUP BY table_layout, table_layout_detail
            ORDER BY 
                table_layout,
                CASE 
                    WHEN table_layout_detail REGEXP '^[0-9]+$' THEN 1
                    ELSE 2
                END,
                CAST(REGEXP_REPLACE(table_layout_detail, '[^0-9]', '') AS UNSIGNED),
                table_layout_detail
        """)
        
        stats = cursor.fetchall()
        cursor.close()
        
        return jsonify({
            'success': True,
            'data': stats
        })
    except Exception as e:
        logger.error(f'獲取桌位統計數據時發生錯誤: {str(e)}')
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/table-details/<table_number>')
@login_required
def get_table_details(table_number):
    """
    獲取特定桌號的詳細訂位記錄
    """
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT 
                contact_name,
                company_name,
                CAST(people_count AS SIGNED) as people_count,
                table_layout,
                table_layout_detail,
                parking,
                DATE_FORMAT(created_at, '%Y-%m-%d %H:%i') as booking_time
            FROM booking_data
            WHERE table_layout_detail = %s
            ORDER BY created_at DESC
        """, (table_number,))
        
        details = cursor.fetchall()
        cursor.close()
        
        return jsonify({
            'success': True,
            'data': details
        })
    except Exception as e:
        logger.error(f'獲取桌位詳細資料時發生錯誤: {str(e)}')
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/parking-stats')
@login_required
def parking_stats():
    """
    停車場統計報表頁面
    """
    return render_template('parking_stats.html')

@app.route('/api/parking-stats')
@login_required
def get_parking_stats():
    """
    獲取停車場統計數據的 API
    """
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # 獲取每個停車場的統計數據
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN parking = '' OR parking IS NULL THEN '未指定'
                    ELSE parking 
                END as parking_lot,
                COUNT(*) as booking_count,
                COALESCE(CAST(SUM(people_count) AS SIGNED), 0) as total_people
            FROM booking_data
            GROUP BY 
                CASE 
                    WHEN parking = '' OR parking IS NULL THEN '未指定'
                    ELSE parking 
                END
            ORDER BY 
                CASE 
                    WHEN parking_lot = '未指定' THEN 'Z'  -- 讓未指定排在最後
                    ELSE parking_lot 
                END
        """)
        
        stats = cursor.fetchall()
        cursor.close()
        
        return jsonify({
            'success': True,
            'data': stats
        })
    except Exception as e:
        logger.error(f'獲取停車場統計數據時發生錯誤: {str(e)}')
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/parking-details/<parking_lot>')
@login_required
def get_parking_details(parking_lot):
    """
    獲取特定停車場的詳細訂位記錄
    """
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        if parking_lot == '未指定':
            cursor.execute("""
                SELECT 
                    contact_name,
                    company_name,
                    CAST(people_count AS SIGNED) as people_count,
                    table_layout,
                    table_layout_detail
                FROM booking_data
                WHERE parking IS NULL OR parking = ''
                ORDER BY table_layout, table_layout_detail
            """)
        else:
            cursor.execute("""
                SELECT 
                    contact_name,
                    company_name,
                    CAST(people_count AS SIGNED) as people_count,
                    table_layout,
                    table_layout_detail
                FROM booking_data
                WHERE parking = %s
                ORDER BY table_layout, table_layout_detail
            """, (parking_lot,))
        
        details = cursor.fetchall()
        cursor.close()
        
        return jsonify({
            'success': True,
            'data': details
        })
    except Exception as e:
        logger.error(f'獲取停車場詳細資料時發生錯誤: {str(e)}')
        return jsonify({'success': False, 'message': str(e)}), 500

if __name__ == '__main__':
    # from waitress import serve
    # serve(app, host=FLASK_HOST, port=FLASK_PORT)

    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=True)
    # http://10.214.57.66:7860/dashboard
    # ngrok http 127.0.0.1:7860
