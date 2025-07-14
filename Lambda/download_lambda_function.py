import boto3
import openpyxl
from openpyxl.utils import column_index_from_string, get_column_letter
import io
import os
import logging
from datetime import datetime,timedelta
from datetime import date
from datetime import time
import json
import urllib.parse

logger = logging.getLogger()
logger.setLevel(logging.INFO)

#重要度は低いので、lambdaの環境変数から取得
bucket_name=os.getenv("bucket_name")
secrets_manager_arn=os.getenv("secrets_manager_arn")
template_path=os.getenv("template_filepath")

s3 = boto3.client("s3")

def lambda_handler(event, context):
    try:
        logger.info(event)
        headers = {k.lower(): v for k, v in event.get("headers", {}).items()}
        content_type = headers.get("content-type", "")
        if "application/json" in content_type:
            body = json.loads(event["body"])
        else:
            parsed = urllib.parse.parse_qs(event.get("body") or "")
            body = {k: v[0] for k, v in parsed.items()}

        # get assume role arn from secrets manager
        role_arn = get_role_arn_s3()
        logger.info(f"role_arn:{role_arn}")
        if role_arn is None or isinstance(role_arn, dict):
            return response(500, {'error': 'Failed to get role arn', 'detail': role_arn})

        # assume role
        session=get_role(role_arn)
        logger.info(f"session:{session}")
        if isinstance(session,dict) and "error" in session:
            return response(500,session)

        #MyAttendanceFunctionにwork_dateの見渡すことで一覧を取得する
        result = get_attendance_list(body,session)

        # resutlの結果をテンプレートファイルに記述 署名付きURLを発行
        urls = write_list_to_excel(result,session)

        #return response(200, result)
        return response(200, {"url": urls})

    except Exception as e:
        return (500, {'error': str(e)})

def get_role_arn_s3():
    try:
        # Secrets Manager クライアント作成
        sct_mgr = boto3.client(service_name='secretsmanager', region_name='us-east-1')
        
        # Secret 取得
        secret_value = sct_mgr.get_secret_value(SecretId=secrets_manager_arn)
        
        # JSON 文字列を辞書に変換
        secret_dict = json.loads(secret_value['SecretString'])

        # s3_access_role_arn を返す
        return secret_dict['s3_access_role_arn']

    except Exception as e:
        return {"error": str(e)}


def get_role(role_arn):
    try:
        # STS クライアント作成
        sts = boto3.client('sts', region_name='ap-northeast-1')
        # AssumeRole 実行
        response = sts.assume_role(
            RoleArn=role_arn,
            RoleSessionName="s3access",
            # DurationSeconds=900  # ← 必要なら有効化
        )
        
        # 新しいセッション作成
        session = boto3.Session(
            aws_access_key_id=response['Credentials']['AccessKeyId'],
            aws_secret_access_key=response['Credentials']['SecretAccessKey'],
            aws_session_token=response['Credentials']['SessionToken'],
            region_name='ap-northeast-1'
        )
        
        return session

    except Exception as e:
        return {"error": str(e)}

def response(status_code, body_dict):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json; charset=utf-8"
        },
        "body": json.dumps(body_dict, ensure_ascii=False)
    }

def get_attendance_list(body,session):
    try:
        lambda_client = session.client("lambda")

        if body.get("work_date"):
            work_date_obj = datetime.strptime(body["work_date"], "%Y-%m-%d")
            work_date_str = work_date_obj.strftime("%Y-%m-%d")
        else:
            work_date_str = ""

        # payloadは相手のLambdaがAPI Gateway経由でのアクセスを想定していたため、この形にしてリクエストを送る
        payload = {
            "headers": {
                "Content-Type": "application/json"
            },
            "body": json.dumps({
            "user_id": "iamuser",
            "work_date": work_date_str,
            'day_of_the_week': "",
            'work_style': "",
            'start_time': "",
            'end_time': "",
            'break_time': "",
            'work_time': "",
            'note': ""
            })
        }

        response = lambda_client.invoke(
            FunctionName="MyAttendanceFunction",
            InvocationType="RequestResponse",
            Payload=json.dumps(payload)
        )
        
        response_payload = json.loads(response["Payload"].read())

        # 呼び出し先 Lambda の body 部分をパース
        nested_body = response_payload.get("body")
        if nested_body:
            parsed_body = json.loads(nested_body)
        else:
            parsed_body = {}

        # records を直接取り出す
        records = parsed_body.get("records", [])

        return {
            "message": parsed_body.get("message", "Success"),
            "records": records
        }
    
    except Exception as e:
        logger.info(f"error:{str(e)}")
        return {
            "statusCode": 500,
            "body": str(e)
        }

def write_list_to_excel(result,session):
    try:
        # テンプレート取得
        s3_client = session.client('s3')
        response = s3_client.get_object(Bucket=bucket_name, Key=template_path)
        template_data = response["Body"].read()
        in_mem_file = io.BytesIO(template_data)

        # Excel 読み込み
        workbook = openpyxl.load_workbook(in_mem_file)
        sheet = workbook.active
        start_row = 8  # 書き込み開始行（テンプレートに合わせて適宜変更）

        #上部
        #年度
        sheet["B5"] = datetime.strptime(result["records"][0]["work_date"].replace("-", "/"), "%Y/%m/%d")
        #指名

        #一覧部分
        for idx, record in enumerate(result["records"]):
            row = start_row + idx

            # 例として以下のカラムに書く
            sheet[f"B{row}"] = record.get("work_date", "")
            sheet[f"C{row}"] = record.get("day_of_the_week", "")
            sheet[f"D{row}"] = record.get("work_style", "")
            sheet[f"E{row}"] = datetime.strptime(record.get("start_time", ""),"%H:%M").time() if record.get("start_time", "") else None
            sheet[f"F{row}"] = datetime.strptime(record.get("end_time", ""),"%H:%M").time() if record.get("end_time", "") else None
            sheet[f"G{row}"] = datetime.strptime(record.get("break_time", ""),"%H:%M").time() if record.get("break_time", "") else None
            sheet[f"H{row}"] = datetime.strptime(record.get("work_time", ""),"%H:%M").time() if record.get("work_time", "") else None
            sheet[f"I{row}"] = record.get("note", "")

        # 書き込み後、ファイルをバイトデータに保存
        out_mem_file = io.BytesIO()
        workbook.save(out_mem_file)
        out_mem_file.seek(0)  # 先頭に戻す

        # putobject
        date_obj = datetime.strptime(result["records"][0]["work_date"], "%Y-%m-%d")
        formatted = date_obj.strftime("%Y%m")

        s3_client.put_object(
            Bucket=bucket_name,
            Key=f"attendance/files/downloads/勤務表_{formatted}.xlsx",
            Body=out_mem_file.getvalue()
        )

        # 署名付きURLの発行
        url = s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket_name, "Key": f"attendance/files/downloads/勤務表_{formatted}.xlsx"},
                ExpiresIn=3600
            )
        
        return url

    except Exception as e:
        logger.info(f"error:{str(e)}")
        return {
            "statusCode": 500,
            "body": str(e)
        }    


# curl https://app.itononari.xyz/download -XPOST -H "Content-Type: application/json" -d '{"work_date":"2025-07-04", "start_time":"09:00", "end_time":"18:15"}'

