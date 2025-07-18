import json
import urllib.parse
import urllib.request
import jwt
import os
import logging
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

redirecturi = os.getenv("redirecturi")
clientid = os.getenv("clientid")
userpoolid = os.getenv("userpoolid")
cognitodomain = os.getenv("cognitodomain")
region = "ap-northeast-1"

def lambda_handler(event, context):
    params = event.get("queryStringParameters") or {}
    code = params.get("code")
    if not code:
        return {"statusCode": 400, "body": "Missing code"}

    token_url = f"https://{cognitodomain}/oauth2/token"
    data = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "client_id": clientid,
        "code": code,
        "redirect_uri": redirecturi
    }).encode()

    req = urllib.request.Request(token_url, data, headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req) as res:
            body = json.loads(res.read())
    except Exception as e:
        logger.error(f"Token exchange failed: {e}")
        return {"statusCode": 500, "body": "Token exchange failed"}

    id_token = body.get("id_token")
    if not id_token:
        return {"statusCode": 401, "body": "No id_token"}

    jwks_url = f"https://cognito-idp.{region}.amazonaws.com/{userpoolid}/.well-known/jwks.json"
    jwks_client = jwt.PyJWKClient(jwks_url)
    signing_key = jwks_client.get_signing_key_from_jwt(id_token)

    decoded = jwt.decode(
        id_token,
        signing_key.key,
        algorithms=["RS256"],
        audience=clientid,
        issuer=f"https://cognito-idp.{region}.amazonaws.com/{userpoolid}"
    )

    # sub email id_token アクセス時間をdynamoDBに記述する
    try:
        payload = {
            "headers": {
                "Content-Type": "application/json"
            },
            "idtoken": id_token,
            "invokefunction": "Authenticate Function"
        }
        
        lambda_client = boto3.client("lambda")
        response = lambda_client.invoke(
            FunctionName='CheckCredentialFunction',
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
            )
        payload_str=response["Payload"].read().decode("utf-8")
        payload_dict=json.loads(payload_str)
        body_str = payload_dict.get("body", "{}")
        body_dict = json.loads(body_str)
        email = body_dict.get("email")


    except Exception as e:
        logger.error(f"Check Credential failed: {e}")
        return {"statusCode": 500, "body": "Check Credential failed"}


    

    # ここで HTML を生成
    html_body = f"""
    <!DOCTYPE html>
    <html lang="ja">
    <head>
      <meta charset="UTF-8" />
      <title>認証完了</title>
    </head>
    <body>
      <p>認証完了しました。リダイレクト中...</p>
      <script>
        const idToken = "{id_token}";
        const email = "{email}";
        localStorage.setItem("id_token", idToken);
        localStorage.setItem("email", email);
        window.location.href = "https://app.itononari.xyz/";
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

