import boto3
from boto3.dynamodb.conditions import Key
import os
import logging
from datetime import datetime
import json
import urllib.parse
import jwt

logger = logging.getLogger()
logger.setLevel(logging.INFO)

#重要度は低いので、lambdaの環境変数から取得
secrets_manager_arn=os.getenv("secrets_manager_arn")
userpoolid = os.getenv("userpoolid")
region = "ap-northeast-1"
clientid = os.getenv("clientid")

# =====
# <Input>
# --body--
# idtoken       : アクセスユーザのAuthentication Headerから送られてきたtoken
# invokefunction: 呼び出し元のFunction名
# 
# <Output>
# Boolean       :認証の成功可否
# 
# --Success--
# Response code :200
# 
# result        :true
# 
# --Failed--
# Response code :401
#
# result        :false
# =====

def lambda_handler(event, context):
    try:
        logger.info(event)
        headers = {k.lower(): v for k, v in event.get("headers", {}).items()}
        content_type = headers.get("content-type", "")
        if "application/json" in content_type:
            body = json.loads(event["body"])
        else:
            # x-www-form-urlencoded → dict(list) → dict(str)
            parsed = urllib.parse.parse_qs(event.get("body") or "")
            body = {k: v[0] for k, v in parsed.items()}


        role_arn = get_role_arn_dynamo()
        logger.info(f"role_arn:{role_arn}")
        if role_arn is None or isinstance(role_arn, dict):
            return response(500, {'error': 'Failed to get role arn', 'detail': role_arn})

        # assume role
        session=get_role(role_arn)
        logger.info(f"session:{session}")
        if isinstance(session,dict) and "error" in session:
            return response(500,session)

        # tokenからsubとemailを抽出
        invokefunction = body.get("invokefunction",None)
        if not invokefunction:
            return {"statusCode": 401, "body": "No function name"}
        idtoken = body.get("idtoken",None)
        if not idtoken:
            return {"statusCode": 401, "body": "No id_token"}

        jwks_url = f"https://cognito-idp.{region}.amazonaws.com/{userpoolid}/.well-known/jwks.json"
        jwks_client = jwt.PyJWKClient(jwks_url)
        signing_key = jwks_client.get_signing_key_from_jwt(idtoken)

        decoded = jwt.decode(
            idtoken,
            signing_key.key,
            algorithms=["RS256"],
            audience=clientid,
            issuer=f"https://cognito-idp.{region}.amazonaws.com/{userpoolid}"
        ) 
        sub = decoded.get("sub")
        email = decoded.get("email")

        # Class
        access = accessrecord(
            idtoken=idtoken,
            sub=sub,
            email=email,
            invokefunctionname=invokefunction,
            lastaccesstime=None
        )
        logger.info(f"access:{access}")

        return response(200, access)
        
    except Exception as e:
        return response(401, {'error': str(e)})

def get_role_arn_dynamo():
    try:
        sct_mgr = boto3.client(service_name='secretsmanager',region_name='us-east-1')
        sct_mgr_iam_role_arn = sct_mgr.get_secret_value(
            SecretId=secrets_manager_arn
        )
        secret_dict= json.loads(sct_mgr_iam_role_arn['SecretString'])
        return secret_dict['dynamo_db_access_role_arn']

    except Exception as e:
        return str(e)

def get_role(role_arn):
    try:
        sts = boto3.client('sts',region_name='ap-northeast-1')
        response = sts.assume_role(
            RoleArn=role_arn,
            RoleSessionName="accessdynamo",
            #DurationSecond=900
            
        )
        session = boto3.Session(aws_access_key_id=response['Credentials']['AccessKeyId'],
                                aws_secret_access_key=response['Credentials']['SecretAccessKey'],
                                aws_session_token=response['Credentials']['SessionToken'],
                                region_name='ap-northeast-1')
        return session
    except Exception as e:
        return  {"error": str(e)}
    
def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json; charset=utf-8"
        },
        "body": json.dumps(body, default=str)
    }

# dynamo dbへ書き込み
def write_AccessAndUserManagr(event,session,):
    client = session.client('dynamodb')
    table_name = 'AccessAndUserManageRecord'

    try:
        response = client.put_item(
            TableName=table_name,
            Item={
                'user_id': {'S': 'iamuser'},
                'work_date': {'S': work_record.work_date.strftime("%Y-%m-%d") if work_record.work_date else ""},
                'day_of_the_week': {'S': str(work_record.day_of_the_week) if work_record.day_of_the_week else ""},
                'work_style': {'S': str(work_record.work_style) if work_record.work_style else ""},
                'start_time': {'S': work_record.start_time.strftime("%H:%M") if work_record.start_time else ""},
                'end_time': {'S': work_record.end_time.strftime("%H:%M") if work_record.end_time else ""},
                'break_time': {'S': format_timedelta(work_record.break_time)  if work_record.break_time else ""},
                'work_time': {'S': format_timedelta(work_record.work_time)  if work_record.work_time else ""},
                'note': {'S': str(work_record.note) if work_record.note else ""}
            }
        )
        logger.info(f"[success]write:{response}")
    except Exception as e:
        logger.error(f"[error]write: write db failed - {str(e)}")
        return {'error': str(e)}

class accessrecord:
    def __init__(self, 
                idtoken=None,
                sub=None,
                email=None,
                invokefunctionname=None,
                lastaccesstime=None):

        # idtoken
        self.idtoken = str(idtoken) if idtoken else None

        # sub
        self.sub = str(sub) if sub else None

        # email
        self.email = str(email) if email else None

        # invoke function
        self.invokefunctionname = invokefunctionname if invokefunctionname else None

        # lastaccesstime    DynameDB書き込み時にセットする想定だがとりあえずここで入れておく
        now = datetime.now()
        self.lastaccesstime = now.strftime("%Y-%m-%d %H:%M:%S")

    def __str__(self):
        return f"""idtoken: {self.idtoken},
                sub: {self.sub},
                email: {self.email}
                invokefunctionname: {self.invokefunctionname},
                lastaccesstime: {self.lastaccesstime}"""

