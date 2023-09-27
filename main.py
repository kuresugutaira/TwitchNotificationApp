import functions_framework
from flask import jsonify, Request, make_response
import hmac
import hashlib
from utils import get_env_vars
from dotenv import load_dotenv
import requests
import json


class NotificationData:
    broadcast_title: str
    broadcaster_user_login_id: str
    broadcaster_user_name: str
    broadcaster_user_id: str
    broadcast_game_name: str
    broadcast_game_id: str
    game_box_art_url: str

    def __init__(self, broadcast_title: str, broadcaster_user_login_id: str, broadcaster_user_name: str,
                 broadcaster_user_id: str, broadcast_game_name: str, broadcast_game_id: str, game_box_art_url: str):
        self.broadcast_title = broadcast_title
        self.broadcaster_user_login_id = broadcaster_user_login_id
        self.broadcaster_user_name = broadcaster_user_name
        self.broadcaster_user_id = broadcaster_user_id
        self.broadcast_game_name = broadcast_game_name
        self.broadcast_game_id = broadcast_game_id
        self.game_box_art_url = game_box_art_url

# Twitchのリクエストに含まれるシグネチャとこちらで生成したシグネチャが一致するかどうか確認する関数


def isValidSignature(request: Request, secret: str) -> bool:
    headers = dict(request.headers)  # リクエストのヘッダー
    body = request.get_data(as_text=True)  # リクエストのボディ
    secret_key = bytearray(secret, "ASCII")  # 秘密鍵
    hmac_msg = (headers["Twitch-Eventsub-Message-Id"] +
                headers["Twitch-Eventsub-Message-Timestamp"] + body).encode("utf-8")
    # hmac_sha256で生成された期待値とヘッダー部のシグネチャが一致したら信頼できる通信であると言える
    expected_signature = "sha256=" + \
        hmac.new(secret_key, hmac_msg, hashlib.sha256).hexdigest()
    header_signature = headers["Twitch-Eventsub-Message-Signature"]
    return hmac.compare_digest(expected_signature, header_signature)

# TwitchのAPIを叩くためのアクセストークンを取得して返す関数


def getAccessToken(twitch_client_id: str, twitch_client_secret: str, get_access_token_url: str) -> str:
    get_access_token_body: dict[str, str] = {
        'client_id': twitch_client_id,
        'client_secret': twitch_client_secret,
        'grant_type': 'client_credentials'
    }
    get_access_token_header: dict[str, str] = {
        'content-type': 'application/x-www-form-urlencoded'
    }
    print("Twitch APIのApp Access Tokenを取得します")
    access_token = ((requests.post(get_access_token_url, headers=get_access_token_header,
                    data=get_access_token_body)).json())["access_token"]
    if access_token:
        print("App Access Tokenの取得に成功しました")
    return access_token

# DiscordのWebhookを呼び出してレスポンスを返す関数


def notifyToDiscord(data: NotificationData, discord_webhook_url: str, discord_icon_url: str) -> requests.Response:
    discord_webhook_body = {
        "content": "配信が始まったヨ！",
        "embeds": [
            {
                "title": data.broadcast_title,
                "url": f"https://www.twitch.tv/{data.broadcaster_user_login_id}",
                "color": 5814783,
                "fields": [
                    {
                        "name": "Playing",
                        "value": data.broadcast_game_name
                    }
                ],
                "author": {
                    "name": f"{data.broadcaster_user_name}({data.broadcaster_user_login_id})"
                },
                "thumbnail": {
                    "url": data.game_box_art_url
                }
            }
        ],
        "username": "Twitch配信通知bot",
        "avatar_url": discord_icon_url,
        "attachments": []
    }
    discord_response = requests.post(discord_webhook_url,
                                     headers={
                                         "Content-Type": "application/json"},
                                     data=json.dumps(discord_webhook_body).encode())
    return discord_response

# TwitchのAPIを叩いて配信者のチャンネル情報を取得する


def getChannelInfo(api_url: str, access_token: str, broadcaster_user_id: str, twitch_client_id: str) -> dict:
    channel_data = requests.get(api_url,
                                params={"broadcaster_id": broadcaster_user_id},
                                headers={"client-id": twitch_client_id, "authorization": f"Bearer {access_token}"})
    return (channel_data.json())["data"][0]


@functions_framework.http
def webhook(request: Request):

    # .envファイルがあるならそこから環境変数を取り出す
    load_dotenv()
    # 環境変数から各値を取り出す
    SECRET: str = get_env_vars("SECRET")
    DISCORD_WEBHOOK_URL: str = get_env_vars("DISCORD_WEBHOOK_URL")
    TWITCH_CLIENT_ID: str = get_env_vars("TWITCH_CLIENT_ID")
    TWITCH_CLIENT_SECRET: str = get_env_vars("TWITCH_CLIENT_SECRET")
    GET_CHANNEL_INFO_URL: str = get_env_vars("GET_CHANNEL_INFO_URL")
    GET_GAME_INFO_URL: str = get_env_vars("GET_GAME_INFO_URL")
    GET_ACCESS_TOKEN_URL: str = get_env_vars("GET_ACCESS_TOKEN_URL")
    DISCORD_ICON_URL: str = get_env_vars("DISCORD_ICON_URL")

    try:
        # シグネチャを確認する
        print("シグネチャを確認します")
        if not isValidSignature(request, SECRET):
            print("シグネチャが不正です")
            return jsonify({"message": "Signature is invalid."}), 403
        print("シグネチャの一致を確認しました")
        # http methodがPOSTであることを確認する
        if request.method == "POST":
            headers = dict(request.headers)
            data = request.json
            # 通知の種類で処理を分ける
            # Subscription要求のコールバックの処理
            if headers["Twitch-Eventsub-Message-Type"] == "webhook_callback_verification":
                print("通知の種類は「Webhookコールバック検証」です")
                challenge = data["challenge"]
                if challenge is not None:
                    response_data = make_response(challenge, 200)
                    response_data.mimetype = "text/plain"
                    print("サブスクリプション要求のコールバックに対してのチャレンジが完了しました")
                    return response_data, 200
                else:
                    print("Challengeが見つかりませんでした")
                    return jsonify({"error": "Challenge not found"}), 400

            elif headers["Twitch-Eventsub-Message-Type"] == "notification":
                print("通知の種類は「配信通知」です")

                # コールバック呼び出しからチャンネル情報を取得
                event_data = data["event"]
                # 配信者のID
                broadcaster_user_id: str = event_data["broadcaster_user_id"]
                # 配信者の表示名
                broadcaster_user_name: str = event_data["broadcaster_user_name"]
                # 配信者のTwitchログインID
                broadcaster_user_login_id: str = event_data["broadcaster_user_login"]

                # APIを叩くためのアクセストークンを得る
                access_token: str = getAccessToken(
                    TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET, GET_ACCESS_TOKEN_URL)

                # 配信者IDからAPIを叩いてチャンネル情報を取得
                channel_data = getChannelInfo(
                    GET_CHANNEL_INFO_URL, access_token, broadcaster_user_id, TWITCH_CLIENT_ID)
                broadcast_game_id: str = channel_data["game_id"]  # 配信するゲームのID
                # 配信するゲームの名前
                broadcast_game_name: str = channel_data["game_name"]
                broadcast_title: str = channel_data["title"]  # 配信タイトル

                # ゲームIDからAPIを叩いてゲーム情報を取得
                game_data = requests.get(GET_GAME_INFO_URL,
                                         params={"id": broadcast_game_id},
                                         headers={"client-id": TWITCH_CLIENT_ID, "authorization": f"Bearer {access_token}"})
                game_data = game_data.json()

                # ゲームのアイコンのURL
                game_box_art_url: str = game_data["data"][0]["box_art_url"]
                game_box_art_url = game_box_art_url.replace(
                    "-{width}x{height}", "")  # widthとheightの指定はしないのでURLから削除する

                print("ゲーム情報の取得を行いました")

                # 配信情報を格納するクラスのインスタンス
                notifi_data: NotificationData = NotificationData(broadcast_title, broadcaster_user_login_id, broadcaster_user_name, broadcaster_user_id,
                                                                 broadcast_game_name, broadcast_game_id, game_box_art_url)

                # DiscordのWebhookを呼ぶ
                discord_response = notifyToDiscord(
                    notifi_data, DISCORD_WEBHOOK_URL, DISCORD_ICON_URL)

                if discord_response.status_code == 204:
                    return jsonify({"message": "Request handled."}), 200
                else:
                    print(discord_response.text)
                    return jsonify({"message": "ログを確認してください"}), 400

            elif headers["Twitch-Eventsub-Message-Type"] == "revocation":
                print("通知の種類は「サブスクリプション破棄通知」です")

                # サブスクを破棄された配信者のIDと破棄理由の取得
                reason: str = data["subscription"]["status"]
                broadcaster_user_id: str = data["subscription"]["condition"]["broadcaster_user_id"]

                # APIを叩くためのアクセストークンを得る
                access_token: str = getAccessToken(
                    TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET, GET_ACCESS_TOKEN_URL)

                # サブスクを破棄された配信者のチャンネル情報を取得する
                channel_data = getChannelInfo(
                    GET_CHANNEL_INFO_URL, access_token, broadcaster_user_id, TWITCH_CLIENT_ID)
                broadcaster_user_login_id: str = channel_data["broadcaster_login"]

                print(f"{broadcaster_user_login_id}のサブスクリプションが{reason}によって破棄されました")

                return jsonify({"message": "Request handled."}), 200

            else:
                print("HeaderのMessage-Typeが不正です")
                return jsonify({"message": "Header is invalid."}), 400

        else:
            print("HTTPメソッドが不正です")
            return jsonify({"message": "Method not allowed."}), 405
    except Exception as e:
        print(f'error : {e}')
        return jsonify({"error": str(e)}), 500
