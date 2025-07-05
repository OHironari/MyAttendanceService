import boto3
from boto3.dynamodb.conditions import Key
import openpyxl
from openpyxl.utils import column_index_from_string, get_column_letter
import io
import os
import logging
from datetime import datetime,timedelta
from datetime import date
from datetime import time
import re
import json
import urllib.parse
import calendar

logger = logging.getLogger()
logger.setLevel(logging.INFO)

#重要度は低いので、lambdaの環境変数から取得
bucket_name=os.getenv("bucket_name")
secrets_manager_arn=os.getenv("secrets_manager_arn")

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
        # Class
        work_record = workrecord(
            work_date=body["work_date"],
            day_of_the_week=body["day_of_the_week"],
            work_style=body["work_style"],
            start_time=body["start_time"],
            end_time=body["end_time"],
            work_time=body["work_time"],
            break_time=body["break_time"],
            note=body["note"],
        )
        logger.info(f"work_record:{work_record}")

        # Input Check
        check=Input_Check(work_record)
        if check:
            return response(500, {'error': check,
                                    'work_date': work_record.work_date,
                                    'start_time': work_record.start_time,
                                    'end_time': work_record.end_time})

        # get assume role arn from secrets manager
        role_arn = get_role_arn_dynamo()
        logger.info(f"role_arn:{role_arn}")
        if role_arn is None or isinstance(role_arn, dict):
            return response(500, {'error': 'Failed to get role arn', 'detail': role_arn})

        # assume role
        session=get_role(role_arn)
        logger.info(f"session:{session}")
        if isinstance(session,dict) and "error" in session:
            return response(500,session)

        # S3 からDynamoへ移行する
        # result = main_logic(event,session,work_record)
        result = write_AttendanceRecords(event,session,work_record)
        result = read_AttendanceRecord(event,session,work_record)

        # 取得した中で日付が欠落していたらレコードを自動生成する
        if work_record.work_date:
            search_year = int(work_record.work_date.strftime("%Y"))
            search_month = int(work_record.work_date.strftime("%m"))
        else:
            search_year = int(datetime.combine(date.today(), time.min).strftime("%Y"))
            search_month = int(datetime.combine(date.today(), time.min).strftime("%m"))
        lack_days = check_month_dates(result['records'], search_year, search_month).get("missing_dates",[])
        if lack_days:
            for lack_day in lack_days:
                # classの定義
                work_record_lack_day = workrecord(work_date=lack_day)
                logger.info(f"lackday[{lack_day}]:{work_record_lack_day}")
                result = write_AttendanceRecords(event,session,work_record_lack_day)
            # 改めて一覧を取得しにいく 引数にはPOST時の日付を使えば多分大丈夫
            result = read_AttendanceRecord(event,session,work_record)


        return response(200, result)
        
    except Exception as e:
        return response(500, {'error': str(e)})

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

def Input_Check(work_record):
    #入力時間チェック
    if work_record.start_time != None and work_record.end_time != None:
        if work_record.start_time > work_record.end_time:
            return 'end_time before start_time'


# file編集　
# 7/4 ダウンロード時のファイル作成で使用したいかな
def main_logic(event,session,work_record):
    try:
        # S3 client
        s3_client = session.client('s3')
        object_key = 'attendance_202507.xlsx'
        object_path = f"attendance/files/{object_key}"
        logger.info(f"対象ファイル: s3://{bucket_name}/{object_path}")

        # 1️⃣ S3からファイルをダウンロード（メモリ上）
        response = s3_client.get_object(Bucket=bucket_name, Key=object_path)
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


        # 一覧の情報を全て取得して返却する
        records = []
        for row in sheet["B8:I38"]:
            date_cell = row[0]
            day_of_the_week_cell = row[1]
            work_style_cell = row[2]
            start_cell = row[3]
            end_cell = row[4]
            break_time_cell = row[5]
            work_time_cell = row[6]
            note_cell = row[7]

            # 仮の日付で time → datetime に変換
            start_dt = datetime.combine(date.today(), start_cell.value) if isinstance(start_cell.value, time) else None
            end_dt = datetime.combine(date.today(), end_cell.value) if isinstance(end_cell.value, time) else None
            break_td = timedelta(hours=break_time_cell.value.hour, minutes=break_time_cell.value.minute) if isinstance(break_time_cell.value, time) else timedelta()

            if start_dt and end_dt:
                work_duration = end_dt - start_dt - break_td
                work_time_str = str(work_duration)
            else:
                work_time_str = ""

            if isinstance(date_cell.value, (datetime, date)):
                records.append({
                    "date": date_cell.value.strftime("%Y-%m-%d"),
                    "day_of_the_week": str(day_of_the_week_cell.value),
                    "work_style": str(work_style_cell.value),
                    "start": start_cell.value.strftime("%H:%M") if isinstance(start_cell.value, time) else (start_cell.value or ""),
                    "end": end_cell.value.strftime("%H:%M") if isinstance(end_cell.value, time) else (end_cell.value or ""),
                    "break_time": break_time_cell.value.strftime("%H:%M") if isinstance(break_time_cell.value, time) else (break_time_cell.value or ""),
                    "work_time": work_time_str,
                    "note":str(note_cell.value) if note_cell.value else (note_cell.value or ""),
                })

        # 編集後をメモリに書き込む
        out_mem_file = io.BytesIO()
        workbook.save(out_mem_file)
        out_mem_file.seek(0)

        # S3にアップロード（上書き or 別ファイルにする場合はOBJECT_KEYを変える）
        s3_client.put_object(Bucket=bucket_name, Key=object_path, Body=out_mem_file.getvalue())

        return {'message': 's3 upload successfully',
                    'records': records
        }
    
    except Exception as e:
        logger.error(f"Error in main_logic: {e}")
        return {'message': 'failed in main logic', 'error': str(e)}


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json; charset=utf-8"
        },
        "body": json.dumps(body, default=str)
    }

#曜日の取得
def get_weekday_abbr(dt: datetime) -> str:
    return dt.strftime("%a")


# dynamo db
def write_AttendanceRecords(event,session,work_record):
    client = session.client('dynamodb')
    table_name = 'AttendanceRecords'

    # まず初回起動時はDBの取得のみ
    try:
        #work_dateがあれば入力
        if work_record.work_date:
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

def read_AttendanceRecord(event,session,work_record):
    # work_recordの値がnullの時は今月の一覧を出力する
    # Read
    client = session.client('dynamodb')
    table_name = 'AttendanceRecords'
    try:
        if work_record.work_date:
            search_day = work_record.work_date.strftime("%Y-%m")
        else:
            search_day = datetime.combine(date.today(), time.min).strftime("%Y-%m")

        result = client.query(
            TableName=table_name,
            KeyConditionExpression='user_id = :uid AND begins_with(work_date, :wdate)',
            ExpressionAttributeValues={
                ':uid': {'S': 'iamuser'},
                ':wdate': {'S': search_day}
            }
        )

        items = result.get('Items', [])
        parsed_items = [convert_dynamo_item(item) for item in items]

        if parsed_items:
            logger.info(f"[success]read:{parsed_items}")
        else:
            logger.info("no record")
            parsed_items = []

        return {
            'message': 'dbread successfully',
            'records': parsed_items
        }

    except Exception as e:
        logger.error(f"[error]read: {str(e)}")
        return {'error': str(e)}

def convert_dynamo_item(item):
    return {k: list(v.values())[0] for k, v in item.items()}

def format_timedelta(td):
    if not isinstance(td, timedelta):
        return ""
    total_minutes = int(td.total_seconds() // 60)
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return f"{hours:02d}:{minutes:02d}"


# 不足している日付取得
def check_month_dates(records, year, month):
# records が list かつ最初の要素が list なら flatten
    # records 内の work_date を set にする
    work_dates = set()
    for r in records:
        if 'work_date' in r and r['work_date']:
            work_dates.add(r['work_date'])
    # 指定年月の全日付を生成
    num_days = calendar.monthrange(year, month)[1]
    all_dates = set(
        date(year, month, day).strftime("%Y-%m-%d") for day in range(1, num_days + 1)
    )
    # 不足している日付を確認
    missing_dates = sorted(all_dates - work_dates)

    return {
        "all_present": len(missing_dates) == 0,
        "missing_dates": missing_dates
    }


class workrecord:
    def __init__(self, 
                work_date=None,
                day_of_the_week=None,
                work_style=None,
                start_time=None,
                end_time=None,
                work_time=None,
                break_time=None,
                note=None):

        # Work Date
        self.work_date = datetime.strptime(work_date, "%Y-%m-%d") if work_date else None

        # Day of the week
        self.day_of_the_week = get_weekday_abbr(self.work_date) if self.work_date else None

        # work style
        if work_style:
            self.work_style = str(work_style)
        else:
            if self.day_of_the_week in ("Sat","Sun"):
                self.work_style = "休み"
            else:
                self.work_style = "出勤"

        # start time
        if self.work_style == "休み":
            self.start_time = None
        else:
            self.start_time = datetime.strptime(start_time, "%H:%M").time() if start_time else time(9, 0)

        # end time
        if self.work_style == "休み":
            self.end_time = None
        else:
            self.end_time = datetime.strptime(end_time, "%H:%M").time() if end_time else time(17, 30)

        # break time のセット（先に設定する）
        if self.work_style == "休み":
            self.break_time = None
        elif break_time:
            bt = datetime.strptime(break_time, "%H:%M")
            self.break_time = timedelta(hours=bt.hour, minutes=bt.minute)          
        else:
            self.break_time = self.calculate_break_minutes(self.start_time, self.end_time)

        # work time（timedelta型で保持）
        if self.work_style == "休み":
            self.work_time = None
        else:
            self.work_time = self.calculate_work_time()

        # note
        self.note = str(note) if note else None

    def __str__(self):
        date_str = self.work_date.strftime("%Y-%m-%d") if self.work_date else None
        day_of_the_week_str = str(self.day_of_the_week)
        work_style_str = str(self.work_style)
        start_str = self.start_time.strftime("%H:%M") if self.start_time else None
        end_str = self.end_time.strftime("%H:%M") if self.end_time else None
        break_time_str = str(self.break_time) if self.break_time else None
        work_time_str = str(self.work_time) if self.work_time else None
        note_str = str(self.note)
        return f"""Date cell: {date_str},
                Day_of_the_week: {day_of_the_week_str},
                Work_style: {work_style_str}
                Start: {start_str},
                End: {end_str},
                Break_time {break_time_str},
                Work_time {work_time_str},
                Note: {note_str}"""

    # ===== work time の時間計算 =====
    def calculate_work_time(self):
        try:
            start_dt = datetime.combine(date.today(), self.start_time)
            end_dt = datetime.combine(date.today(), self.end_time)
            if end_dt < start_dt:
                end_dt += timedelta(days=1)
            return end_dt - start_dt - self.break_time
        except Exception as e:
            print(f"Work time calculation error: {e}")
            return None

    # ===== 休憩時間関係の計算 =====
    def overlap_minutes(self, start1, end1, start2, end2):
        latest_start = max(start1, start2)
        earliest_end = min(end1, end2)
        delta = (earliest_end - latest_start).total_seconds()
        return max(0, delta / 60)

    def calculate_break_minutes(self, start_time_obj, end_time_obj):
        base_date = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)

        start_time = datetime.combine(base_date, start_time_obj)
        end_time = datetime.combine(base_date, end_time_obj)
        if end_time < start_time:
            end_time += timedelta(days=1)

        total_break_minutes = 0
        for b_start, b_end in self.bread_periods():
            b_start_dt = datetime.combine(base_date, b_start)
            b_end_dt = datetime.combine(base_date, b_end)

            # 終了時刻が開始時刻より小さい場合（深夜跨ぎ）
            if b_end < b_start:
                b_end_dt += timedelta(days=1)

            # 同じく必要なら b_start も補正
            if b_start_dt > b_end_dt:
                b_start_dt += timedelta(days=1)

            total_break_minutes += self.overlap_minutes(start_time, end_time, b_start_dt, b_end_dt)

        return timedelta(minutes=total_break_minutes)

    def parse_time(self, tstr):
        return datetime.strptime(tstr, "%H:%M").time()

    def bread_periods(self):
        return [
            (self.parse_time("12:00"), self.parse_time("12:45")),
            (self.parse_time("17:30"), self.parse_time("17:45")),
            (self.parse_time("19:00"), self.parse_time("19:30")),
            (self.parse_time("21:30"), self.parse_time("21:45")),
            (self.parse_time("23:45"), self.parse_time("00:15")),
            (self.parse_time("03:15"), self.parse_time("03:45")),
            (self.parse_time("05:45"), self.parse_time("06:15")),
        ]
# curl https://app.itononari.xyz/submit -XPOST -H "Content-Type: application/json" -d '{"work_date":"2025-07-04", "start_time":"09:00", "end_time":"18:15"}'

