from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    FlexSendMessage, ImageSendMessage, TemplateSendMessage,
    PostbackAction, URIAction, MessageAction,
    ButtonsTemplate, CarouselTemplate, CarouselColumn,
    ConfirmTemplate, StickerMessage, AudioMessage,
    VideoMessage, FileMessage, LocationMessage
)
from linebot.v3.messaging import ShowLoadingAnimationRequest
import os
from dotenv import load_dotenv
import mysql.connector
from datetime import datetime
from openai import AzureOpenAI
import json
import pandas as pd
import requests

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

PARKING_IMAGES = {
    "P1": "P1_park.png",
    "P2": "P2_park.png",
    "P3": "P3_park.png",
    "P4": "P4_park.png",
    "P5": "P5_park.png",
    "P6": "P6_park.png"
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
            return TextSendMessage(text="查無資料，請根據報名時填寫的姓名全名或公司名稱查詢")
        
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
                            "text": booking['contact_name'][0]+"O"+booking['contact_name'][-1:],
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
                                "label": f"{booking['parking']}停車場位置",
                                "text": f"{booking['parking']}停車場"
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
            alt_text='座位查詢結果',
            contents={
                "type": "carousel",
                "contents": carousel_contents
            }
        )
        
        return flex_message
        
    except Exception as e:
        return TextSendMessage(text="查詢過程中發生錯誤，請稍後再試。")

def get_chat_history(user_id: str) -> list:
    """
    獲取用戶最近的10筆對話歷史，排除 carousel 類型的回應和座位查詢
    """
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        query = """
            SELECT LOG_CONTENT as user_content, LOG_RESPONSE as assistant_content 
            FROM GREATEN_LINEBOT_V1_LOG 
            WHERE LOG_USER = %s 
            AND LOG_CONTENT != '座位查詢'
            AND LOG_RESPONSE NOT LIKE '%{"type": "carousel"%'
            ORDER BY LOG_DATE DESC 
            LIMIT 10
        """
        cursor.execute(query, (user_id,))
        results = cursor.fetchall()
        
        # 將結果轉換為 OpenAI 格式的對話歷史
        chat_history = []
        for record in reversed(results):  # 反轉順序以保持時間順序
            chat_history.append({"role": "user", "content": record['user_content']})
            chat_history.append({"role": "assistant", "content": record['assistant_content']})
            
        return chat_history
        
    except mysql.connector.Error as err:
        print(f"獲取對話歷史時發生錯誤: {err}")
        return []
    finally:
        cursor.close()
        connection.close()

def get_last_query(user_id: str) -> str:
    """
    獲取用戶最後一次查詢的內容
    """
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        query = """
            SELECT LOG_CONTENT as user_content
            FROM GREATEN_LINEBOT_V1_LOG 
            WHERE LOG_USER = %s 
            ORDER BY LOG_DATE DESC 
            LIMIT 1
        """
        cursor.execute(query, (user_id,))
        result = cursor.fetchone()
        
        return result['user_content'] if result else None
        
    except mysql.connector.Error as err:
        print(f"獲取最後查詢記錄時發生錯誤: {err}")
        return None
    finally:
        cursor.close()
        connection.close()

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
        user_id = event.source.user_id
        response_message = None

        # 獲取用戶語言設定
        try:
            profile = line_bot_api.get_profile(user_id)
            user_language = profile.language or 'zh-tw'  # 如果沒有設定語言，預設使用繁體中文
        except Exception as e:
            print(f"獲取用戶資料時發生錯誤: {e}")
            user_language = 'zh-tw'  # 發生錯誤時使用預設語言

        # 檢查是否為直接輸入姓名或公司名稱（上一次是座位查詢）
        last_query = get_last_query(user_id)
        if last_query == "座位查詢" and not user_message.startswith('查詢 ') and len(user_message.strip()) >= 2:
            # 顯示載入動畫
            send_loading_animation(user_id)
            # 自動加上"查詢"前綴
            search_term = user_message.strip()
            response_message = search_booking(search_term)
            line_bot_api.reply_message(event.reply_token, response_message)
            
            # 儲存對話紀錄
            log_data = {
                'LOG_ID': datetime.now().strftime('%Y%m%d%H%M%S'),
                'MODEL_ID': 'LINE_BOT_V1',
                'USER_ID': user_id,
                'INPUT': f"查詢 {search_term}"  # 儲存完整的查詢指令
            }
            
            # 將回應訊息轉換為字串格式
            if isinstance(response_message, TextSendMessage):
                response_str = response_message.text
            elif isinstance(response_message, ImageSendMessage):
                response_str = response_message.original_content_url
            elif isinstance(response_message, FlexSendMessage):
                # 直接使用 as_json_dict() 方法獲取可序列化的字典
                response_str = json.dumps(response_message.contents.as_json_dict(), ensure_ascii=False)
            
            save_server_log(log_data, response_str)
            return

        # 根據不同的訊息內容回覆不同的訊息
        if any(user_message.startswith(f"{p}停車場") for p in ["P1", "P2", "P3", "P4", "P5", "P6"]):
            # 取得停車場編號
            parking_number = user_message[:2]  # 獲取 P1-P6
            # 回覆對應停車場圖片
            image_url = f"{BASE_IMAGE_URL}/images/{PARKING_IMAGES[parking_number]}"
            image_message = ImageSendMessage(
                original_content_url=image_url,
                preview_image_url=image_url
            )
            response_message = image_message
            line_bot_api.reply_message(event.reply_token, image_message)
        elif user_message == '座位區':
            # 回覆停車場圖片
            image_url = f"{BASE_IMAGE_URL}/images/20250226table.jpg"
            image_message = ImageSendMessage(
                original_content_url=image_url,
                preview_image_url=image_url
            )
            response_message = image_message
            line_bot_api.reply_message(event.reply_token, image_message)
            
        elif user_message == '座位查詢':
            # 回覆查詢預約的引導訊息
            guide_message = """請輸入要查詢的姓名或公司名稱"""
            response_message = TextSendMessage(text=guide_message)
            line_bot_api.reply_message(event.reply_token, response_message)

        else:
            # 顯示載入動畫（因為 OpenAI 回應可能需要一些時間）
            send_loading_animation(user_id, loading_seconds=8)
            # 獲取用戶的歷史對話記錄
            chat_history = get_chat_history(user_id)
            response_message = openai_with_tools(user_message, user_language, chat_history)
            line_bot_api.reply_message(event.reply_token, response_message)

        # 儲存對話紀錄
        log_data = {
            'LOG_ID': datetime.now().strftime('%Y%m%d%H%M%S'),
            'MODEL_ID': 'LINE_BOT_V1',
            'USER_ID': user_id,
            'INPUT': user_message
        }
        
        # 將回應訊息轉換為字串格式
        response_str = ''
        if isinstance(response_message, TextSendMessage):
            response_str = response_message.text
        elif isinstance(response_message, ImageSendMessage):
            response_str = response_message.original_content_url
        elif isinstance(response_message, FlexSendMessage):
            # 直接使用 as_json_dict() 方法獲取可序列化的字典
            response_str = json.dumps(response_message.contents.as_json_dict(), ensure_ascii=False)
        
        save_server_log(log_data, response_str)

    @handler.add(MessageEvent, message=(StickerMessage, AudioMessage, VideoMessage, FileMessage, LocationMessage))
    def handle_non_text_message(event):
        """
        處理非文字訊息
        """
        message_type = event.message.type
        response_text = "不好意思，目前我只能處理文字訊息。"
        
        if message_type == 'sticker':
            response_text = "很抱歉，我目前無法處理貼圖訊息，請使用文字與我溝通。"
        elif message_type == 'audio':
            response_text = "抱歉，我目前無法處理語音訊息，請以文字形式告訴我您的需求。"
        elif message_type == 'video':
            response_text = "抱歉，我目前無法處理影片訊息，請使用文字與我溝通。"
        elif message_type == 'file':
            response_text = "抱歉，我目前無法處理檔案，請直接用文字告訴我您的需求。"
        elif message_type == 'location':
            response_text = "抱歉，我目前無法處理位置資訊，請使用文字描述您的需求。"
            
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=response_text)
        )

    # 可以在這裡添加更多的 LINE 相關路由和處理函數

def save_server_log(data: dict, res: str) -> None:
    connection = get_db_connection()

    try:
        data = {
            "LOG_DATE": str(datetime.now()),
            "LOG_ID": str(data['LOG_ID']),
            "LOG_MODEL_ID": str(data['MODEL_ID']),
            "LOG_USER": str(data['USER_ID']),
            "LOG_CONTENT": str(data['INPUT']),
            "LOG_RESPONSE": str(res),
            "LOG_OBJECT": 'completion'
        }
    except KeyError as e:  # 捕獲具體的 KeyError
        missing_key = str(e)  # 獲取缺失的鍵名
        data = {
            "LOG_DATE": str(datetime.now()),
            "LOG_ID": str(data['LOG_ID']),
            "LOG_MODEL_ID": str(data['MODEL_ID']),
            "LOG_USER": str(data['USER_ID']),
            "LOG_CONTENT": str(data['INPUT']),
            "LOG_RESPONSE": str(res),
            "LOG_OBJECT": f'KeyError_{missing_key}'  # 在錯誤訊息中包含缺失的欄位名稱
        }
    cursor = connection.cursor()

    # 插入資料的 SQL 語句
    insert_sql = """INSERT INTO `GREATEN_LINEBOT_V1_LOG`
    (`LOG_DATE`,
    `LOG_ID`,
    `LOG_MODEL_ID`,
    `LOG_USER`,
    `LOG_CONTENT`,
    `LOG_RESPONSE`,
    `LOG_OBJECT`)
    VALUES
    (%(LOG_DATE)s,
    %(LOG_ID)s,
    %(LOG_MODEL_ID)s,
    %(LOG_USER)s,
    %(LOG_CONTENT)s,
    %(LOG_RESPONSE)s,
    %(LOG_OBJECT)s);"""

    try:
        cursor.execute(insert_sql, data)
        connection.commit()
    except mysql.connector.Error as err:
        print(f"資料庫錯誤: {err}")
        connection.rollback()
    finally:
        cursor.close()
        connection.close()

def openai_with_tools(user_input, language, chat_history):
    """
    整合了原始 OpenAI 模型和工具功能的函數
    """
    OPENAI_API_KEY=os.getenv('OPENAI_API_KEY', '')
    OPENAI_API_VERSION=os.getenv('OPENAI_API_VERSION', '')
    AZURE_OPENAI_ENDPOINT=os.getenv('AZURE_OPENAI_ENDPOINT', '')
    client = AzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=OPENAI_API_KEY,
        api_version=OPENAI_API_VERSION
    )

    # 讀取系統提示詞
    with open(os.path.join(os.path.dirname(__file__), 'greaten_systemword_v1.txt'), 'r', encoding='utf-8') as f1:
        systemwords_1 = f1.read()
    systemwords_1 = systemwords_1.format(language=language)
    
    # 構建提示詞列表
    prompts = [{"role": "system", "content": systemwords_1}]
    for item in chat_history:
        prompts.append(item)
    prompts.append({"role": "user", "content": user_input})

    # 定義工具
    tools = [
        {
            "type": "function",
            "function": {
                "name": "search_booking",
                "description": "搜尋訂位資料，根據姓名或公司名稱查詢",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "search_term": {
                            "type": "string",
                            "description": "要搜尋的姓名或公司名稱",
                        },
                    },
                    "required": ["search_term"],
                },
            }
        }
    ]

    # 創建回應
    response = client.chat.completions.create(
        model='gpt4o',
        messages=prompts,
        tools=tools,
        tool_choice="auto",
        temperature=0.2,
    )
    
    response_message = response.choices[0].message

    # 處理工具調用
    if response_message.tool_calls:
        functions_def = {
            "search_booking": search_booking
        }
        for tool_call in response_message.tool_calls:
            function_name = tool_call.function.name
            if tool_call.function.name in functions_def:
                function_args = json.loads(tool_call.function.arguments)
                function_response = functions_def[function_name](
                    search_term=function_args.get("search_term")
                )
                return function_response  # 直接返回函數的回應（FlexMessage 或 TextMessage）
    
    # 如果沒有工具調用，返回一般回應
    return TextSendMessage(text=response_message.content)

def send_loading_animation(user_id, loading_seconds=5):
    """發送載入動畫到 LINE 聊天室
    
    Args:
        user_id (str): LINE 用戶 ID
        loading_seconds (int, optional): 載入動畫顯示時間（秒）。必須是 5 的倍數。預設為 5 秒。
    """
    # 確保 loading_seconds 是 5 的倍數
    loading_seconds = ((loading_seconds + 4) // 5) * 5
    
    url = "https://api.line.me/v2/bot/chat/loading/start"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.getenv('LINE_CHANNEL_ACCESS_TOKEN', '')}",
    }
    
    data = {
        "chatId": user_id,
        "loadingSeconds": loading_seconds
    }

    try:
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 202:
            print(f"成功發送載入動畫給用戶 {user_id}")
        else:
            print(f"發送載入動畫失敗: {response.status_code}, {response.text}")
    except Exception as e:
        print(f"發送載入動畫時發生錯誤: {str(e)}")
