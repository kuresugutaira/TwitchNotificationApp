import requests
import json
from utils.utils import getEnvVars, getAccessToken
from dotenv import load_dotenv

load_dotenv()

TWITCH_CLIENT_ID: str = getEnvVars("TWITCH_CLIENT_ID")
TWITCH_CLIENT_SECRET: str = getEnvVars("TWITCH_CLIENT_SECRET")
GET_ACCESS_TOKEN_URL: str = getEnvVars("GET_ACCESS_TOKEN_URL")
SECRET: str = getEnvVars("SECRET")
CALLBACK_URL: str = getEnvVars("CALLBACK_URL")

# APIを叩くのに必要なTwitch App Tokenを取得する
twitch_access_token: str = getAccessToken(
    TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET, GET_ACCESS_TOKEN_URL)

# TwitchのnameからuserID(ユニークID)をAPIをたたいて取得する
# ここでユーザーIDを入力する
subscribe_target_name: str = ''

get_userID_url: str = 'https://api.twitch.tv/helix/users'
get_userID_payload: dict[str, str] = {
    'login': subscribe_target_name
}
get_userID_header: dict[str, str] = {
    'client-id': TWITCH_CLIENT_ID,
    'content-type': 'application/json',
    'authorization': f'Bearer {twitch_access_token}'
}

response = requests.get(
    get_userID_url, params=get_userID_payload, headers=get_userID_header)
data = response.json()
target_userID: str = data['data'][0]['id']

print(data)

# 配信通知のサブスク登録を行う
subscribe_url: str = 'https://api.twitch.tv/helix/eventsub/subscriptions'
subscribe_header: dict[str, str] = {
    'content-type': 'application/json',
    'client-id': TWITCH_CLIENT_ID,
    'authorization': f'Bearer {twitch_access_token}'
}
subscribe_payload = {
    'type': 'stream.online',
    'version': '1',
    'condition': {
        'broadcaster_user_id': target_userID
    },
    'transport': {
        'method': 'webhook',
        'callback': CALLBACK_URL,
        'secret': SECRET
    }
}

# サブスク登録のリクエストに対するレスポンスを表示
response = requests.post(subscribe_url, data=json.dumps(
    subscribe_payload), headers=subscribe_header)
data = response.json()
print(data)
