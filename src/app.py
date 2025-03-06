from flask import Flask, send_from_directory, send_file, render_template, request, redirect, url_for, session, jsonify
from flask_cors import CORS
import os
from dotenv import load_dotenv
from flask_mysqldb import MySQL
import mysql.connector
from functools import wraps
import time
import pandas as pd
from io import BytesIO
from datetime import datetime
from werkzeug.utils import secure_filename

#line
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, FlexSendMessage, TextSendMessage, ImageSendMessage, TemplateSendMessage, PostbackAction, URIAction, MessageAction, ButtonsTemplate, CarouselTemplate,  CarouselColumn, ConfirmTemplate


# 載入 .env 變數
load_dotenv()

app = Flask(__name__)
CORS(app)

FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
FLASK_PORT = os.getenv("FLASK_PORT", "")
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}

# 設定 Session 密鑰
app.secret_key = 'your_secret_key_here'  # 請更換為安全的密鑰

# MySQL 設定
MYSQL_HOST = os.getenv('MYSQL_HOST', '10.214.57.11')
MYSQL_USER= os.getenv('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', 'root1231')
MYSQL_DB= os.getenv('MYSQL_DB', 'greatenDB')
MYSQL_PORT= os.getenv('MYSQL_PORT', 3306)
MYSQL_CONNECT_TIMEOUT= 120
MYSQL_CURSORCLASS= 'DictCursor'
# mysql = MySQL(app)

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

# def get_db_connection():
#     return mysql.connector.connect(
#         host="10.214.57.11",
#         user="root",
#         password="root1231",
#         database="greatenDB"
#     )

def get_db_connection(max_retries=5, retry_delay=5):
    """獲取資料庫連線，包含重試機制"""
    for attempt in range(max_retries):
        try:
            app.logger.info(f'嘗試連接資料庫 (第 {attempt + 1} 次)')
            app.logger.info(f'連線設定: HOST={MYSQL_HOST}, PORT={MYSQL_PORT}, DB={MYSQL_DB}')
            
            connection = mysql.connector.connect(
                host=MYSQL_HOST,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                database=MYSQL_DB,
                port=MYSQL_PORT
            )

            # 測試連線
            cursor = connection.cursor()
            cursor.execute('SELECT 1')
            cursor.fetchall()  # 讀取測試查詢的結果
            cursor.close()     # 關閉測試用的游標
            
            app.logger.info('資料庫連線成功')
            return connection
            
        except Exception as e:
            app.logger.error(f'資料庫連線嘗試 {attempt + 1}/{max_retries} 失敗')
            app.logger.error(f'錯誤類型: {type(e).__name__}')
            app.logger.error(f'錯誤訊息: {str(e)}')
            app.logger.error(f'錯誤詳情: {repr(e)}')
            
            if attempt < max_retries - 1:
                app.logger.info(f'等待 {retry_delay} 秒後重試...')
                time.sleep(retry_delay)
            else:
                app.logger.error('已達最大重試次數，放棄連線')
                raise

# 設定圖片上傳資料夾
app.config['UPLOAD_FOLDER'] = 'images'

# 確保圖片資料夾存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/')
def index():
    """
    提供首頁
    """
    try:
        # 記錄首頁請求
        app.logger.info('收到首頁請求')
        return send_file('index.html')
    except Exception as e:
        app.logger.error(f'提供首頁時發生錯誤: {str(e)}')
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
        
        connection = mysql.connector.connect(
            host="10.214.57.11",       # 数据库主机，例如 "localhost"
            user="root",   # 数据库用户名
            password="root1231",  # 数据库密码
            database="greatenDB"  # 要连接的数据库名称
        )

        # 创建游标对象
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
        app.logger.error(f'更新資料時發生錯誤: {str(e)}')
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
        
        app.logger.info(f'使用者嘗試登入: {username}')
        
        try:
            app.logger.info('開始建立資料庫連線')
            connection = mysql.connector.connect(
            host="10.214.57.11",       # 数据库主机，例如 "localhost"
            user="root",   # 数据库用户名
            password="root1231",  # 数据库密码
            database="greatenDB"  # 要连接的数据库名称
        )

        # 创建游标对象
            cursor = connection.cursor(dictionary=True)
            
            app.logger.info('執行使用者查詢')
            cursor.execute("""
                SELECT id, username, password, full_name 
                FROM users 
                WHERE username = %s AND is_active = TRUE
            """, (username,))
            
            user = cursor.fetchone()
            cursor.close()
            
            app.logger.info(f'查詢結果: {"成功" if user else "未找到使用者"}')
            
            if user and user['password'] == password:  # 使用字典鍵值存取
                app.logger.info(f'使用者 {username} 登入成功')
                session['logged_in'] = True
                session['user_id'] = user['id']  # 使用字典鍵值存取
                session['username'] = user['username']  # 使用字典鍵值存取
                session['full_name'] = user['full_name']  # 使用字典鍵值存取
                return redirect(url_for('dashboard'))
            else:
                app.logger.warning(f'使用者 {username} 登入失敗: 帳號或密碼錯誤')
                error = '帳號或密碼錯誤'
                
        except Exception as e:
            app.logger.error('登入過程中發生錯誤')
            app.logger.error(f'錯誤類型: {type(e).__name__}')
            app.logger.error(f'錯誤訊息: {str(e)}')
            app.logger.error(f'錯誤詳情: {repr(e)}')
            app.logger.error(f'使用者資料: {user if "user" in locals() else "未取得"}')  # 添加更多診斷資訊
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
    if 'file' not in request.files:
        return '沒有檔案', 400
    
    file = request.files['file']
    if file.filename == '':
        return '沒有選擇檔案', 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        try:
            df = pd.read_excel(filepath)
            connection = mysql.connector.connect(
            host="10.214.57.11",       # 数据库主机，例如 "localhost"
            user="root",   # 数据库用户名
            password="root1231",  # 数据库密码
            database="greatenDB"  # 要连接的数据库名称
        )

        # 创建游标对象
            cursor = connection.cursor()
            
            # 檢查必要欄位是否存在
            required_columns = ['姓名', '公司名稱', '人數', '區域', '桌位圖', '停車場']
            if not all(col in df.columns for col in required_columns):
                return 'Excel 檔案格式不正確，請使用正確的範本', 400
            
            # 插入資料
            for _, row in df.iterrows():
                sql = """
                    INSERT INTO booking_data 
                    ( contact_name, company_name, people_count, table_layout, table_layout_detail, parking)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """
                cursor.execute(sql, (
                    row['姓名'],
                    row['公司名稱'],
                    row['人數'],
                    row['區域'],
                    row['桌位圖'],
                    row['停車場']
                ))
            
            connection.commit()
            cursor.close()
            
            return '檔案上傳成功', 200
        except Exception as e:
            app.logger.error(f'處理檔案時發生錯誤: {str(e)}')
            return f'處理檔案時發生錯誤: {str(e)}', 500
        finally:
            # 清理上傳的檔案
            os.remove(filepath)
    
    return '不支援的檔案類型', 400

@app.route('/export_data', methods=['GET'])
@login_required
def export_data():
    """
    匯出訂位資料為 Excel
    """
    try:
        connection = mysql.connector.connect(
            host="10.214.57.11",       # 数据库主机，例如 "localhost"
            user="root",   # 数据库用户名
            password="root1231",  # 数据库密码
            database="greatenDB"  # 要连接的数据库名称
        )

        # 创建游标对象
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
        app.logger.error('匯出資料時發生錯誤')
        app.logger.error(f'錯誤類型: {type(e).__name__}')
        app.logger.error(f'錯誤訊息: {str(e)}')
        return jsonify({'error': '匯出資料時發生錯誤'}), 500


@app.route('/delete/<int:id>', methods=['DELETE'])
@login_required
def delete_item(id):
    """
    刪除指定的訂位資料
    """
    try:
        connection = mysql.connector.connect(
            host="10.214.57.11",       # 数据库主机，例如 "localhost"
            user="root",   # 数据库用户名
            password="root1231",  # 数据库密码
            database="greatenDB"  # 要连接的数据库名称
        )

        # 创建游标对象
        cursor = connection.cursor()
        cursor.execute("DELETE FROM booking_data WHERE id = %s", (id,))
        connection.commit()
        cursor.close()
        return '刪除成功', 200
    except Exception as e:
        app.logger.error(f'刪除資料時發生錯誤: {str(e)}')
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
        app.logger.error(f'下載範本時發生錯誤: {str(e)}')
        return '範本檔案不存在，請聯繫系統管理員', 500

@app.route('/add_booking', methods=['POST'])
@login_required
def add_booking():
    """
    新增單筆訂位資料
    """
    try:
        data = request.json
        app.logger.info(f'新增訂位資料: {data}')
        
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
        
        connection = mysql.connector.connect(
            host="10.214.57.11",       # 数据库主机，例如 "localhost"
            user="root",   # 数据库用户名
            password="root1231",  # 数据库密码
            database="greatenDB"  # 要连接的数据库名称
        )
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
        
        app.logger.info(f'訂位資料新增成功: {data}')
        return jsonify({
            'success': True,
            'message': '新增成功'
        })
    except Exception as e:
        app.logger.error(f'新增訂位資料時發生錯誤: {str(e)}')
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

        connection = mysql.connector.connect(
            host="10.214.57.11",
            user="root",
            password="root1231",
            database="greatenDB"
        )
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
        app.logger.error(f'批量刪除資料時發生錯誤: {str(e)}')
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
        
        app.logger.info(f'報表查詢參數: start_date={start_date}, end_date={end_date}')
        
        connection = mysql.connector.connect(
            host="10.214.57.11",       # 数据库主机，例如 "localhost"
            user="root",   # 数据库用户名
            password="root1231",  # 数据库密码
            database="greatenDB"  # 要连接的数据库名称
        )
        cursor = connection.cursor(dictionary=True)
        
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
        app.logger.info(f'摘要統計結果: {summary}')
        
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
        # app.logger.info(f'區域統計結果: {area_stats}')
        
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
        # app.logger.info(f'每日統計結果: {daily_data}')
        
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
        # app.logger.info(f'人數分布結果: {people_distribution}')
        
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
                AND parking IS NOT NULL 
                AND parking != ''
            GROUP BY parking_lot
            ORDER BY 
                CASE 
                    WHEN parking_lot = '未指定' THEN 999
                    ELSE CAST(SUBSTRING(parking_lot, 2) AS UNSIGNED)
                END
        """, (start_date, end_date))
        
        parking_stats = cursor.fetchall()
        parking_analysis = {
            'lots': [item['parking_lot'] for item in parking_stats],
            'counts': [item['count'] for item in parking_stats]
        }
        # app.logger.info(f'停車場分析結果: {parking_analysis}')
        
        # 公司訂位統計
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
        # app.logger.info(f'公司統計結果: {company_analysis}')
        
        cursor.close()
        
        return jsonify({
            'summary': summary,
            'area_stats': area_stats,
            'daily_stats': daily_data,
            'people_distribution': people_distribution,
            'parking_analysis': parking_analysis,
            'company_analysis': company_analysis
        })
        
    except Exception as e:
        app.logger.error('獲取報表資料時發生錯誤')
        app.logger.error(f'錯誤類型: {type(e).__name__}')
        app.logger.error(f'錯誤訊息: {str(e)}')
        app.logger.error(f'錯誤詳情: {repr(e)}')
        app.logger.error(f'查詢參數: start_date={start_date}, end_date={end_date}')
        return jsonify({'error': str(e)}), 500


@app.route('/dashboard')
@login_required
def dashboard():
    """
    主控台頁面 - 顯示所有訂位資料
    """
    try:
# print("mysql",input)
        # connection = mysql.connector.connect(
        #     host="10.214.57.11",       # 数据库主机，例如 "localhost"
        #     user="root",   # 数据库用户名
        #     password="root1231",  # 数据库密码
        #     database="greatenDB"  # 要连接的数据库名称
        # )
        connection = get_db_connection()
        # 创建游标对象
        cursor = connection.cursor(dictionary=True)

        # 执行查询

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
        
        app.logger.info(f'成功讀取訂位資料，共 {len(data)} 筆記錄')
        return render_template('dashboard.html', data=data)
    except Exception as e:
        app.logger.error('讀取訂位資料時發生錯誤')
        app.logger.error(f'錯誤類型: {type(e).__name__}')
        app.logger.error(f'錯誤訊息: {str(e)}')
        app.logger.error(f'錯誤詳情: {repr(e)}')
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
        app.logger.error(f'獲取統計資料時發生錯誤: {str(e)}')
        return '獲取統計資料時發生錯誤，請稍後再試', 500



@app.route("/search", methods=["GET"])
def search():
    contact_name = request.args.get("contact_name", "").strip()

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

    data = cursor.fetchall()

    cursor.close()
    connection.close()

    return jsonify(data)

if __name__ == '__main__':
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=True)
    # http://10.214.57.66:7860/dashboard
    # ngrok http 127.0.0.1:7860
