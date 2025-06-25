import boto3
import openpyxl
from openpyxl.utils import column_index_from_string, get_column_letter
import io
import os
import logging
from datetime import datetime
from datetime import date
from datetime import time
import re
import json

logger = logging.getLogger()
logger.setLevel(logging.INFO)

#ゆくゆくはSSMからの取得をしたい
bucket_name=os.getenv("bucket_name")
secrets_manager_arn=os.getenv("secrets_manager_arn")
secrets_value_for_iam_role = os.getenv("secrets_value_for_iam_role")

def lambda_handler(event, context):
    try:
        # 将来的にはここにapiからの値を入れる
        work_record = workrecord(
            work_date=None,
            start_time=None,
            end_time=None
        )
        # get assume role arn from secrets manager
        role_arn = get_role_arn()
        if role_arn is None or isinstance(role_arn, dict):
            return response(500, {'error': 'Failed to get role arn', 'detail': role_arn})

        # assume role
        session=get_role(role_arn)
        if isinstance(session,dict) and "error" in session:
            return response(500,session)


        result = main_logic(event,session,work_record)
        return response(200, result)
        
    except Exception as e:
        return response(500, {'error': str(e)})

def get_role_arn():
    try:
        sct_mgr = boto3.client(service_name='secretsmanager',region_name='us-east-1')
        sct_mgr_iam_role_arn = sct_mgr.get_secret_value(
            SecretId=secrets_manager_arn
        )
        secret_dict= json.loads(sct_mgr_iam_role_arn['SecretString'])
        return secret_dict['s3_access_role_arn']

    except Exception as e:
        return str(e)

def get_role(role_arn):
    try:
        sts = boto3.client('sts',region_name='ap-northeast-1')
        response = sts.assume_role(
            RoleArn=role_arn,
            RoleSessionName="accessS3",
            DurationSecond=900
            
        )
        session = boto3.Session(aws_access_key_id=response['Credentials']['AccessKeyId'],
                                aws_secret_access_key=response['Credentials']['SecretAccessKey'],
                                aws_session_token=response['Credentials']['SessionToken'],
                                region_name='ap-northeast-1')
        return session
    except Exception as e:
        return  {"error": str(e)}

def main_logic(event,session,work_record):
    try:
        # S3 client
        s3_client = session.client('s3')
        object_key = 'attendance_202506.xlsx'
        logger.info(f"対象ファイル: s3://{bucket_name}/{object_key}")

        # 1️⃣ S3からファイルをダウンロード（メモリ上）
        response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
        excel_data = response['Body'].read()
        in_mem_file = io.BytesIO(excel_data)

        # Excel読み込み
        workbook = openpyxl.load_workbook(in_mem_file)
        sheet = workbook.active

        # ====== 編集処理 ======
        search_range = sheet["B8:B38"]

        for row in search_range:
            for cell in row:
                cell_value = sheet[cell.coordinate].value

                # セルが datetime または date の場合のみ比較
                if isinstance(cell_value, (datetime, date)):
                    if cell_value.strftime("%Y-%m-%d") == work_record.work_date.strftime("%Y-%m-%d"):

                        # 行番号・列文字の取得
                        col_letters, row_number = re.match(r"([A-Z]+)(\d+)", cell.coordinate).groups()
                        col_num = column_index_from_string(col_letters)
                        row_number = int(row_number)

                        # 列番号を使ってセル位置を計算
                        start_time_cell = f"{get_column_letter(col_num + 3)}{row_number}"
                        end_time_cell = f"{get_column_letter(col_num + 4)}{row_number}"

                        # セルに値をセット（sheet が正しい）
                        sheet[start_time_cell].value = work_record.start_time
                        sheet[end_time_cell].value = work_record.end_time

        # 編集後をメモリに書き込む
        out_mem_file = io.BytesIO()
        workbook.save(out_mem_file)
        out_mem_file.seek(0)

        # S3にアップロード（上書き or 別ファイルにする場合はOBJECT_KEYを変える）
        s3_client.put_object(Bucket=bucket_name, Key=object_key, Body=out_mem_file.getvalue())

        return {'message': 's3 upload successfully'}

    except Exception as e:
        logger.error(f"Error in main_logic: {e}")
        return {'message': 's3 upload failed', 'error': str(e)}


def response(status_code, body):
    logger.info(f'statusCode:{status_code}')
    logger.info(body)
    return


class workrecord:
    def __init__(self, work_date=None, start_time=None, end_time=None):
        if work_date:
            self.work_date = datetime.strptime(work_date, "%Y-%m-%d")
        else:
            self.work_date = datetime.combine(date.today(), time.min)

        if start_time:
            self.start_time = datetime.strptime(start_time, "%H:%M").time()
        else:
            self.start_time = time(9, 0)  # 9:00

        if end_time:
            self.end_time = datetime.strptime(end_time, "%H:%M").time()
        else:
            self.end_time = time(17, 30)  # 17:30
    def __str__(self):
        return f"{self.work_date} | {self.start_time} - {self.end_time} 時間"
