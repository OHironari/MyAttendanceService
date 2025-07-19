import json
import requests
import os
import boto3
import logging
from datetime import datetime

redirecturi = os.getenv("redirecturi")
clientid = os.getenv("clientid")
secrets_manager_arn = os.getenv("secrets_manager_arn")

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    params = event.get("queryStringParameters") or {}
    code = params.get("code")
    client_secret_dict = get_client_secret()
    client_secret = client_secret_dict['client_secret']
    CompanyA = client_secret_dict['CompanyA']
    CompanyB = client_secret_dict['CompanyB']
    gmailaddress = client_secret_dict['gmailaddress']
    name = client_secret_dict['name']
    first_name, last_name = name.split("　")

    # トークン取得
    access_token = get_access_token(code,client_secret)


    # tokens["refresh_token"] を安全に保存 (DB or Secrets Manager)
    logger.info(f"access_token:{access_token}")

    #Gmail 下書き呼び出し
    response = create_gmail_draft(access_token,name,first_name,CompanyA,CompanyB,gmailaddress)

    # draft idの取り出し
    draftid=response.get("message",{}).get("id")

    # ここで HTML を生成
    html_body = f"""
    <!DOCTYPE html>
    <html lang="ja">
    <head>
      <meta charset="UTF-8" />
      <title>認証完了</title>
    </head>
    <body>
      <p>認証完了しました。gmail draftへリダイレクト中...</p>
      <script>
        window.location.href = "https://mail.google.com/mail/u/0/#drafts?compose={draftid}";
      </script>
    </body>
    </html>
    """

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "text/html"
        },
        "body": html_body
    }


def get_client_secret():
    try:
        sct_mgr = boto3.client(service_name='secretsmanager', region_name='us-east-1')
        sct_mgr_iam_role_arn = sct_mgr.get_secret_value(SecretId=secrets_manager_arn)
        secret_dict = json.loads(sct_mgr_iam_role_arn['SecretString'])
        return secret_dict
    except Exception as e:
        logger.info(f"get_client_id error:{str(e)}")
        raise

def get_access_token(code,client_secret):
    try:
        token_url = "https://oauth2.googleapis.com/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "code": code,
            "client_id": clientid,
            "client_secret": client_secret,
            "redirect_uri": redirecturi,
            "grant_type": "authorization_code",
        }

        res = requests.post(token_url,headers=headers,data=data)
        tokens = res.json()
        access_token=tokens["access_token"]
        return access_token

    except Exception as e:
        logger.info(f"get_access_token error:{str(e)}")
        raise

def create_gmail_draft(access_token,name,first_name,CompanyA,CompanyB,gmailaddress):
    import base64
    from email.mime.text import MIMEText

    today = datetime.now()

    # メール本文の作成
    message = MIMEText(f"""お世話になっております。{first_name}です。

{datetime.strftime(today,"%m")}月分の勤務表を提出いたします。

⚫︎{CompanyA}
・作業実績表_{name}_{datetime.strftime(today,"%Y%m")}.xlsx

⚫︎{CompanyB}
・勤怠表_{name}_{datetime.strftime(today,"%Y%m")}.xlsx
・交通費_立替経費精算書_{name}_{datetime.strftime(today,"%Y%m")}.xlsx

ご確認いただけますと幸いです。

以上、よろしくお願いいたします。""")
    message["to"] = gmailaddress
    message["subject"] = f"勤務表提出({datetime.strftime(today,"%m")}月分)_{first_name}"
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

    # Gmail API へのリクエスト
    url = "https://gmail.googleapis.com/gmail/v1/users/me/drafts"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "message": {
            "raw": raw_message
        }
    }

    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()
