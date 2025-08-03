# app/handlers.py
from app.models import workrecord
from app.dynamo_utils import get_role_arn_dynamo, get_role, read_AttendanceRecord, write_AttendanceRecords, check_month_dates,Input_Check
import logging
from datetime import datetime, timedelta, date, time
import json
import urllib.parse

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handle_attendance_request(body: dict,headers):
    #check = check_credential(body["id_token"])
    if check.get("status") == "false":
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

    try:
        content_type = headers.get("content-type", "")
        if "application/json" in content_type:
            body = json.loads(body)
        else:
            parsed = urllib.parse.parse_qs(body or "")
            body = {k: v[0] for k, v in parsed.items()}

        #check = check_credential(body["id_token"])
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

        result = read_AttendanceRecord(session, work_record)

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
                write_AttendanceRecords(session, work_record_lack_day)
            result = read_AttendanceRecord(session, work_record)

        if not body.get("style") == "readonly":
            write_AttendanceRecords(session, work_record)
            result = read_AttendanceRecord(session, work_record)



        return response(200, result)

    except Exception as e:
        return response(500, {"error": str(e), "records": []})



def response(status_code, body):
    return {
        "statusCode": status_code,
        "body": body
    }



# def check_credential(id_token):
#     try:
#         payload = {"idtoken": id_token, "invokefunction": "Attendance Function"}
#         logger.info(f"payload:{payload}")
#         lambda_client = boto3.client("lambda")
#         response = lambda_client.invoke(
#             FunctionName='CheckCredentialFunction',
#             InvocationType='RequestResponse',
#             Payload=json.dumps(payload)
#         )
#         payload_str = response["Payload"].read().decode("utf-8")
#         payload_dict = json.loads(payload_str)
#         body_str = payload_dict.get("body", "{}")
#         body_dict = json.loads(body_str)
#         status_code = payload_dict.get("statusCode", 500)
#         if status_code == 200 and body_dict.get("status") == "online":
#             return {"status": "true", "sub": body_dict.get("sub"), "email": body_dict.get("email")}
#         else:
#             logger.info(f"Invalid credential: {body_dict.get('error', 'Unknown error')}")
#             return {"status": "false"}
#     except Exception as e:
#         logger.info(f"check_credential error: {str(e)}")
#         return {"status": "false"}