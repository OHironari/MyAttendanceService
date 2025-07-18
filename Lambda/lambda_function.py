import boto3
from boto3.dynamodb.conditions import Key
import os
import logging
from datetime import datetime, timedelta, date, time
import json
import urllib.parse
import calendar

logger = logging.getLogger()
logger.setLevel(logging.INFO)

bucket_name = os.getenv("bucket_name")
secrets_manager_arn = os.getenv("secrets_manager_arn")

def lambda_handler(event, context):
    try:
        headers = {k.lower(): v for k, v in event.get("headers", {}).items()}
        content_type = headers.get("content-type", "")
        if "application/json" in content_type:
            body = json.loads(event["body"])
        else:
            parsed = urllib.parse.parse_qs(event.get("body") or "")
            body = {k: v[0] for k, v in parsed.items()}

        check = check_credential(body["id_token"])
        if check.get("status") == "false":
            logger.info("token expired")
            return response(401, {'error': 'token expired', 'records': []})
        sub = check.get("sub")

        work_record = workrecord(
            sub=sub,
            work_date=body.get("work_date", None),
            day_of_the_week=body.get("day_of_the_week", None),
            work_style=body.get("work_style", None),
            start_time=body.get("start_time", None),
            end_time=body.get("end_time", None),
            work_time=body.get("work_time", None),
            break_time=body.get("break_time", None),
            note=body.get("note", None),
            submit=body.get("submit", None)
        )
        logger.info(f"work_record:{work_record}")

        check = Input_Check(work_record)
        if check:
            return response(400, {'error': check, 'records': []})

        role_arn = get_role_arn_dynamo()
        logger.info(f"role_arn:{role_arn}")
        if role_arn is None or isinstance(role_arn, dict):
            return response(500, {'error': 'Failed to get role arn', 'records': []})

        session = get_role(role_arn)
        if isinstance(session, dict) and "error" in session:
            return response(500, {'error': session['error'], 'records': []})

        result = read_AttendanceRecord(event, session, work_record)

        if work_record.work_date:
            search_year = int(work_record.work_date.strftime("%Y"))
            search_month = int(work_record.work_date.strftime("%m"))
        else:
            today = datetime.combine(date.today(), time.min)
            search_year = int(today.strftime("%Y"))
            search_month = int(today.strftime("%m"))

        lack_days = check_month_dates(result['records'], search_year, search_month).get("missing_dates", [])
        if lack_days:
            for lack_day in lack_days:
                work_record_lack_day = workrecord(sub=sub, work_date=lack_day)
                logger.info(f"lackday[{lack_day}]:{work_record_lack_day}")
                write_AttendanceRecords(event, session, work_record_lack_day)
            result = read_AttendanceRecord(event, session, work_record)

        if not body.get("style") == "readonly":
            write_AttendanceRecords(event, session, work_record)
            result = read_AttendanceRecord(event, session, work_record)

        return response(200, result)

    except Exception as e:
        logger.error(f"Exception: {str(e)}")
        return response(500, {'error': str(e), 'records': []})

def get_role_arn_dynamo():
    try:
        sct_mgr = boto3.client(service_name='secretsmanager', region_name='us-east-1')
        sct_mgr_iam_role_arn = sct_mgr.get_secret_value(SecretId=secrets_manager_arn)
        secret_dict = json.loads(sct_mgr_iam_role_arn['SecretString'])
        return secret_dict['dynamo_db_access_role_arn']
    except Exception as e:
        return str(e)

def get_role(role_arn):
    try:
        sts = boto3.client('sts', region_name='ap-northeast-1')
        response = sts.assume_role(RoleArn=role_arn, RoleSessionName="accessdynamo")
        session = boto3.Session(
            aws_access_key_id=response['Credentials']['AccessKeyId'],
            aws_secret_access_key=response['Credentials']['SecretAccessKey'],
            aws_session_token=response['Credentials']['SessionToken'],
            region_name='ap-northeast-1'
        )
        return session
    except Exception as e:
        return {"error": str(e)}

def Input_Check(work_record):
    if work_record.start_time and work_record.end_time:
        if work_record.start_time > work_record.end_time:
            return 'end_time before start_time'

def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json; charset=utf-8"},
        "body": json.dumps(body, default=str)
    }

def get_weekday_abbr(dt: datetime) -> str:
    return dt.strftime("%a")

def write_AttendanceRecords(event, session, work_record):
    client = session.client('dynamodb')
    table_name = 'AttendanceRecords'
    try:
        if work_record.work_date:
            response = client.put_item(
                TableName=table_name,
                Item={
                    'user_id': {'S': str(work_record.sub)},
                    'work_date': {'S': work_record.work_date.strftime("%Y-%m-%d")},
                    'day_of_the_week': {'S': str(work_record.day_of_the_week)},
                    'work_style': {'S': str(work_record.work_style)},
                    'start_time': {'S': work_record.start_time.strftime("%H:%M") if work_record.start_time else ""},
                    'end_time': {'S': work_record.end_time.strftime("%H:%M") if work_record.end_time else ""},
                    'break_time': {'S': format_timedelta(work_record.break_time) if work_record.break_time else ""},
                    'work_time': {'S': format_timedelta(work_record.work_time) if work_record.work_time else ""},
                    'note': {'S': str(work_record.note) if work_record.note else ""},
                    'submit': {'S': str(work_record.submit) if work_record.submit else "0"}
                }
            )
            logger.info(f"[success]write:{response}")
    except Exception as e:
        logger.error(f"[error]write: {str(e)}")

def read_AttendanceRecord(event, session, work_record):
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
                ':uid': {'S': work_record.sub},
                ':wdate': {'S': search_day}
            }
        )

        items = result.get('Items', [])
        parsed_items = [convert_dynamo_item(item) for item in items]

        logger.info(f"[success]read:{parsed_items}")
        return {
            'message': 'dbread successfully',
            'records': parsed_items
        }

    except Exception as e:
        logger.error(f"[error]read: {str(e)}")
        return {'message': 'dbread failed', 'error': str(e), 'records': []}

def convert_dynamo_item(item):
    return {k: list(v.values())[0] for k, v in item.items()}

def format_timedelta(td):
    if not isinstance(td, timedelta):
        return ""
    total_minutes = int(td.total_seconds() // 60)
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return f"{hours:02d}:{minutes:02d}"

def check_month_dates(records, year, month):
    work_dates = set()
    for r in records:
        if 'work_date' in r and r['work_date']:
            work_dates.add(r['work_date'])
    num_days = calendar.monthrange(year, month)[1]
    all_dates = set(date(year, month, day).strftime("%Y-%m-%d") for day in range(1, num_days + 1))
    missing_dates = sorted(all_dates - work_dates)
    return {"all_present": len(missing_dates) == 0, "missing_dates": missing_dates}

class workrecord:
    def __init__(self, sub=None, work_date=None, day_of_the_week=None, work_style=None,
                 start_time=None, end_time=None, work_time=None, break_time=None, note=None, submit=None):
        self.sub = str(sub)
        self.work_date = datetime.strptime(work_date, "%Y-%m-%d") if work_date else None
        self.day_of_the_week = get_weekday_abbr(self.work_date) if self.work_date else None
        if work_style:
            self.work_style = str(work_style)
        else:
            self.work_style = "休み" if self.day_of_the_week in ("Sat", "Sun") else "出勤"
        self.start_time = None if self.work_style == "休み" else datetime.strptime(start_time, "%H:%M").time() if start_time else time(9, 0)
        self.end_time = None if self.work_style == "休み" else datetime.strptime(end_time, "%H:%M").time() if end_time else time(17, 30)
        #self.break_time = None if self.work_style == "休み" else self.calculate_break_minutes(self.start_time, self.end_time)
        if work_style == '休み':
            self.break_time = timedelta()
            self.work_time = None
        elif break_time:
            t = datetime.strptime(break_time, "%H:%M")
            self.break_time = timedelta(hours=t.hour, minutes=t.minute)
        else:
            self.break_time = self.calculate_break_minutes(self.start_time, self.end_time)

        self.work_time = None if self.work_style == "休み" else self.calculate_work_time()
        self.work_time = None if self.work_style == "休み" else self.calculate_work_time()
        self.note = str(note) if note else None
        if datetime.strptime(work_date,"%Y-%m-%d") > datetime.now():
            self.submit = "0"
        else:
            self.submit = str(submit) if submit in ["0", "1"] else "0"

    def __str__(self):
        return f"Sub: {self.sub}, Date: {self.work_date.strftime('%Y-%m-%d') if self.work_date else None}, Day: {self.day_of_the_week}, Style: {self.work_style}, Start: {self.start_time}, End: {self.end_time}, Break: {self.break_time}, Work: {self.work_time}, Note: {self.note}, Submit: {self.submit}"

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
            if b_end < b_start:
                b_end_dt += timedelta(days=1)
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

def check_credential(id_token):
    try:
        payload = {"idtoken": id_token, "invokefunction": "Attendance Function"}
        logger.info(f"payload:{payload}")
        lambda_client = boto3.client("lambda")
        response = lambda_client.invoke(
            FunctionName='CheckCredentialFunction',
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        payload_str = response["Payload"].read().decode("utf-8")
        payload_dict = json.loads(payload_str)
        body_str = payload_dict.get("body", "{}")
        body_dict = json.loads(body_str)
        status_code = payload_dict.get("statusCode", 500)
        if status_code == 200 and body_dict.get("status") == "online":
            return {"status": "true", "sub": body_dict.get("sub"), "email": body_dict.get("email")}
        else:
            logger.info(f"Invalid credential: {body_dict.get('error', 'Unknown error')}")
            return {"status": "false"}
    except Exception as e:
        logger.info(f"check_credential error: {str(e)}")
        return {"status": "false"}