
import logging
import boto3
from boto3.dynamodb.conditions import Key
import json
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta, date, time
import calendar

logger = logging.getLogger()
logger.setLevel(logging.INFO)

secrets_manager_arn = os.getenv("SECRETS_MANAGER_ARN")

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

def write_AttendanceRecords(session, work_record):
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

def read_AttendanceRecord(session, work_record):
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


def check_month_dates(records, year, month):
    work_dates = set()
    for r in records:
        if 'work_date' in r and r['work_date']:
            work_dates.add(r['work_date'])
    num_days = calendar.monthrange(year, month)[1]
    all_dates = set(date(year, month, day).strftime("%Y-%m-%d") for day in range(1, num_days + 1))
    missing_dates = sorted(all_dates - work_dates)
    return {"all_present": len(missing_dates) == 0, "missing_dates": missing_dates}

def format_timedelta(td):
    if not isinstance(td, timedelta):
        return ""
    total_minutes = int(td.total_seconds() // 60)
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return f"{hours:02d}:{minutes:02d}"