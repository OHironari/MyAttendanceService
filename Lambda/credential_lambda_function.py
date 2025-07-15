import boto3
from boto3.dynamodb.conditions import Key
import os
import logging
from datetime import datetime, timedelta
import json
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
# error        :tokenexpired
# =====

def lambda_handler(event, context):
    try:
        # 直接 dict から取得
        idtoken = event.get("idtoken")
        invokefunction = event.get("invokefunction")

        if not invokefunction:
            return {"statusCode": 401, "body": "No function name"}
        if not idtoken:
            return {"statusCode": 401, "body": "No id_token"}

        # 取得に1秒近くかかるので停止
        # role_arn = get_role_arn_dynamo()
        # logger.info(f"role_arn:{role_arn}")
        # if role_arn is None or isinstance(role_arn, dict):
        #     return response(500, {'error': 'Failed to get role arn', 'detail': role_arn})

        # # assume role
        # session=get_role(role_arn)
        # if isinstance(session,dict) and "error" in session:
        #     return response(500,session)

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

        # access recordの書き込み
        # attendance,downloadからの呼び出しはlastaccess checkしてから書き込み
        
        # Authentication
        if invokefunction == "Authenticate Function":
            result=write_AccessAndUserManagr(access)
        elif check_Credential(access):
            result=write_AccessAndUserManagr(access)
        else:
            return response(401,{'status':'token expired'})
        
        return response(200, {'status': 'online'})
        
    except Exception as e:
        return response(401, {'error': str(e)})

# def get_role_arn_dynamo():
#     try:
#         sct_mgr = boto3.client(service_name='secretsmanager',region_name='us-east-1')
#         sct_mgr_iam_role_arn = sct_mgr.get_secret_value(
#             SecretId=secrets_manager_arn
#         )
#         secret_dict= json.loads(sct_mgr_iam_role_arn['SecretString'])
#         return secret_dict['credential_dynamo_access_role_arn']

#     except Exception as e:
#         return str(e)

# def get_role(role_arn):
#     try:
#         sts = boto3.client('sts',region_name='ap-northeast-1')
#         response = sts.assume_role(
#             RoleArn=role_arn,
#             RoleSessionName="accessdynamo",            
#         )
#         session = boto3.Session(aws_access_key_id=response['Credentials']['AccessKeyId'],
#                                 aws_secret_access_key=response['Credentials']['SecretAccessKey'],
#                                 aws_session_token=response['Credentials']['SessionToken'],
#                                 region_name='ap-northeast-1')
#         return session
#     except Exception as e:
#         return  {"error": str(e)}
    
def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json; charset=utf-8"
        },
        "body": json.dumps(body, default=str)
    }

def convert_dynamo_item(item):
    return {k: list(v.values())[0] for k, v in item.items()}

# dynamo dbへ書き込み
def write_AccessAndUserManagr(accessrecord):
    client = boto3.client('dynamodb')
    table_name = 'AccessAndUserManageRecord'

    try:
    #書き込み
        response = client.put_item(
            TableName=table_name,
            Item={
                'sub': {'S': accessrecord.sub},
                'idtoken': {'S': accessrecord.idtoken},
                'email': {'S': accessrecord.email},
                'invokefunctionname': {'S': accessrecord.invokefunctionname},
                'lastaccesstime': {'S': accessrecord.lastaccesstime}
            }
        )
        logger.info(f"[success]write:{response}")
        return response
    except Exception as e:
        logger.error(f"[error]write: write db failed - {str(e)}")
        return {'error': str(e)}

def check_Credential(accessrecord):
    client = boto3.client('dynamodb')
    table_name = 'AccessAndUserManageRecord'
    
    try:
        #tokenの有効性確認
        #現在から1時間以内のもので最新のレコードを取得
        # 今の時間
        now = datetime.now()
        # 1時間前
        one_hour_ago = now - timedelta(hours=1)
        start_time_str = one_hour_ago.strftime("%Y-%m-%d %H:%M:%S")
        

        result = client.query(
            TableName=table_name,
            KeyConditionExpression='#s = :sub AND lastaccesstime >= :start_time',
            ExpressionAttributeNames={
                '#s': 'sub'
            },
            ExpressionAttributeValues={
                ':sub': {'S': accessrecord.sub},
                ':start_time': {'S': start_time_str}
            },
            ScanIndexForward=False,  # 新しい順に並べる
            Limit=1  # 先頭のみ取得
        )

        items = result.get('Items', [])
        parsed_items = [convert_dynamo_item(item) for item in items]

        if parsed_items:
            db_record = parsed_items[0]
            if accessrecord.idtoken != db_record['idtoken']:
                logger.info(f"token mismatch \n dbrecord:{db_record['idtoken']} \n request:{accessrecord.idtoken}")
                return False
            else:
                logger.info("token match")
                return True
        else:
            logger.info("no record within 1h")
            return False
                
    except Exception as e:
        logger.info(f"check_credential_error:{str(e)}")
        return False

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

        # lastaccesstime
        now = datetime.now()
        self.lastaccesstime = now.strftime("%Y-%m-%d %H:%M:%S")

    def __str__(self):
        return f"""idtoken: {self.idtoken},
                sub: {self.sub},
                email: {self.email}
                invokefunctionname: {self.invokefunctionname},
                lastaccesstime: {self.lastaccesstime}"""

