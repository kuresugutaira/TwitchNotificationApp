import os
import requests
from typing import Optional


def getEnvVars(key: str) -> str:
    '''
    環境変数から値を取得する関数
    '''
    var: Optional[str] = os.environ.get(key)
    if var is not None:
        print(key + "の値を取得しました")
        return var
    else:
        print(key + "の値が取得できませんでした")
        exit(1)


def getAccessToken(twitch_client_id: str, twitch_client_secret: str, get_access_token_uri: str) -> str:
    ''' 
    TwitchのAPIを叩くのに必要なトークンを取得する関数

    -----
    Args:
        ``twitch_client_id`` (str) : Twitch DevelopersのClientID\n
        ``twitch_client_secret`` (str) : Twitch DevelopersのClientSecret\n
        ``get_access_token_uri`` (str) : トークンを得るために叩くAPIのURI
    Returns:
        ``access_token`` (str) : トークン
    '''

    request_body: dict[str, str] = {
        'client_id': twitch_client_id,
        'client_secret': twitch_client_secret,
        'grant_type': 'client_credentials'
    }
    request_header: dict[str, str] = {
        'content-type': 'application/x-www-form-urlencoded'
    }
    print("Twitch APIのApp Access Tokenを取得します")
    response: requests.Response = requests.post(
        get_access_token_uri, headers=request_header, data=request_body)
    access_token: str = (response.json())["access_token"]
    if access_token is not None:
        print("App Access Tokenの取得に成功しました")
    else:
        print("App Access Tokenの取得に失敗しました")
    return access_token
