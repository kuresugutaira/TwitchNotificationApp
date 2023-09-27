import os
from typing import Optional


def getEnvVars(key: str) -> Optional[str]:
    '''
    環境変数から値を取得する関数
    '''
    var: Optional[str] = os.environ.get(key)
    if var is not None:
        print(key + "の値を取得しました")
        return var
    else:
        print(key + "の値が取得できませんでした")
        return None
