from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    FlexSendMessage, ImageSendMessage, TemplateSendMessage,
    PostbackAction, URIAction, MessageAction,
    ButtonsTemplate, CarouselTemplate, CarouselColumn,
    ConfirmTemplate
)
import os
from dotenv import load_dotenv
import mysql.connector
from datetime import datetime

# 載入環境變數
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

# LINE Bot 相關設定
line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN', ''))
handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET', ''))

GPS_URL={
    "P1": "https://reurl.cc/zpanl6",
    "P2": "https://reurl.cc/748zkD",
    "P3": "https://reurl.cc/lNWKrA",
    "P4": "https://reurl.cc/04qM9b",
    "P5": "https://reurl.cc/geAXrp",
    "P6": "https://reurl.cc/46zVj2",
    "P7": "https://reurl.cc/46VbyR"
}
# 設定圖片的基礎 URL
BASE_IMAGE_URL = os.getenv('NGROK_URL', '')

def get_db_connection():
    """獲取資料庫連線"""
    return mysql.connector.connect(
        host=os.getenv('MYSQL_HOST', '10.214.57.11'),
        user=os.getenv('MYSQL_USER', 'root'),
        password=os.getenv('MYSQL_PASSWORD', 'root1231'),
        database=os.getenv('MYSQL_DB', 'greatenDB')
    )

def search_booking(search_term):
    """搜尋訂位資料"""
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        query = """
            SELECT 
                contact_name,
                company_name,
                people_count,
                table_layout,
                table_layout_detail,
                parking,
                created_at
            FROM booking_data 
            WHERE contact_name = %s 
            OR company_name LIKE %s 
            ORDER BY created_at DESC
        """
        cursor.execute(query, (search_term, f'%{search_term}%'))
        results = cursor.fetchall()
        cursor.close()
        connection.close()
        
        if not results:
            return TextSendMessage(text="抱歉，找不到相關的訂位資料。")
        
        # 如果結果超過5筆，使用文字格式
        if len(results) > 5:
            response = "查詢結果如下：\n\n"
            for booking in results:
                response += f"姓名：{booking['contact_name']}\n"
                response += f"公司：{booking['company_name']}\n"
                response += f"人數：{booking['people_count']}人\n"
                response += f"區域：{booking['table_layout']}\n"
                response += f"桌位：{booking['table_layout_detail']}\n"
                response += f"停車場：{booking['parking'] if booking['parking'] else '無'}\n"
                response += "--------------------\n"
            return TextSendMessage(text=response)
        
        # 5筆以內使用 Flex Message
        carousel_contents = []
        
        for booking in results:
            bubble = {
                "type": "bubble",
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "spacing": "sm",
                    "contents": [
                        {
                            "type": "text",
                            "text": booking['contact_name'],
                            "weight": "bold",
                            "size": "xl",
                            "wrap": True,
                            "contents": []
                        },
                        {
                            "type": "box",
                            "layout": "baseline",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": "公司",
                                    "weight": "bold",
                                    "size": "xl",
                                    "flex": 0,
                                    "wrap": True,
                                    "contents": []
                                },
                                {
                                    "type": "text",
                                    "text": booking['company_name'],
                                    "align": "center",
                                    "contents": []
                                }
                            ]
                        },
                        {
                            "type": "box",
                            "layout": "baseline",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": "人數",
                                    "weight": "bold",
                                    "size": "lg",
                                    "flex": 0,
                                    "wrap": True,
                                    "contents": []
                                },
                                {
                                    "type": "text",
                                    "text": f"{booking['people_count']}人",
                                    "align": "end",
                                    "contents": []
                                }
                            ]
                        },
                        {
                            "type": "box",
                            "layout": "baseline",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": "區域",
                                    "weight": "bold",
                                    "size": "lg",
                                    "flex": 0,
                                    "wrap": True,
                                    "contents": []
                                },
                                {
                                    "type": "text",
                                    "text": booking['table_layout'],
                                    "align": "end",
                                    "contents": []
                                }
                            ]
                        },
                        {
                            "type": "box",
                            "layout": "baseline",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": "桌位",
                                    "weight": "bold",
                                    "size": "xxl",
                                    "flex": 0,
                                    "wrap": True,
                                    "contents": []
                                },
                                {
                                    "type": "text",
                                    "text": booking['table_layout_detail'],
                                    "weight": "bold",
                                    "size": "xl",
                                    "color": "#041AFCFF",
                                    "align": "end",
                                    "contents": []
                                }
                            ]
                        },
                        {
                            "type": "box",
                            "layout": "baseline",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": "停車場",
                                    "weight": "bold",
                                    "size": "xxl",
                                    "flex": 0,
                                    "wrap": True,
                                    "contents": []
                                },
                                {
                                    "type": "text",
                                    "text": booking['parking'] if booking['parking'] else "無",
                                    "weight": "bold",
                                    "size": "xl",
                                    "color": "#FC0404FF",
                                    "align": "end",
                                    "contents": []
                                }
                            ]
                        }
                    ]
                },
                "footer": {
                    "type": "box",
                    "layout": "vertical",
                    "spacing": "sm",
                    "contents": [
                        {
                            "type": "button",
                            "action": {
                                "type": "message",
                                "label": "停車場位置",
                                "text": "停車場"
                            },
                            "color": "#1B9C0DFF",
                            "margin": "lg",
                            "height": "md",
                            "style": "primary"
                        },
                        {
                            "type": "button",
                            "action": {
                                "type": "uri",
                                "label": "導航至停車場位置",
                                "uri": GPS_URL[booking['parking']]
                            },
                            "color": "#704809FF",
                            "margin": "lg",
                            "height": "md",
                            "style": "primary"
                        }
                    ]
                }
            }
            carousel_contents.append(bubble)
        
        flex_message = FlexSendMessage(
            alt_text='訂位查詢結果',
            contents={
                "type": "carousel",
                "contents": carousel_contents
            }
        )
        
        return flex_message
        
    except Exception as e:
        return TextSendMessage(text="查詢過程中發生錯誤，請稍後再試。")

def init_line_routes(app):
    @app.route("/callback", methods=['POST'])
    def callback():
        """
        LINE Webhook 回調處理
        """
        # 獲取 X-Line-Signature 頭部值
        signature = request.headers['X-Line-Signature']

        # 獲取請求體文字
        body = request.get_data(as_text=True)
        app.logger.info("Request body: " + body)

        try:
            # 驗證簽名並處理請求
            handler.handle(body, signature)
        except InvalidSignatureError:
            app.logger.error("Invalid signature. Please check your channel access token/channel secret.")
            abort(400)

        return 'OK'

    @handler.add(MessageEvent, message=TextMessage)
    def handle_message(event):
        """
        處理文字訊息
        """
        # 獲取用戶發送的訊息
        user_message = event.message.text

        # 根據不同的訊息內容回覆不同的訊息
        if user_message == '停車場':
            # 回覆停車場圖片
            image_url = f"{BASE_IMAGE_URL}/images/park_v4.png"
            image_message = ImageSendMessage(
                original_content_url=image_url,
                preview_image_url=image_url
            )
            line_bot_api.reply_message(event.reply_token, image_message)
        elif user_message == '座位區':
            # 回覆停車場圖片
            image_url = f"{BASE_IMAGE_URL}/images/20250226table.jpg"
            image_message = ImageSendMessage(
                original_content_url=image_url,
                preview_image_url=image_url
            )
            line_bot_api.reply_message(event.reply_token, image_message)
            
        elif user_message == '座位查詢':
            # 回覆查詢預約的引導訊息
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=
                                """請輸入要查詢的姓名或公司名稱：  
範例：
查詢 李某  
查詢 桂田集團""")
            )

        elif user_message.startswith('查詢 '):
            # 處理查詢請求
            search_term = user_message[3:].strip()  # 移除 "查詢 " 前綴
            if len(search_term) < 2:
                response_message = "請輸入至少兩個字的姓名或公司名稱。"
            else:
                response_message = search_booking(search_term)
            
            line_bot_api.reply_message(
                event.reply_token,
                response_message
            )


    # 可以在這裡添加更多的 LINE 相關路由和處理函數