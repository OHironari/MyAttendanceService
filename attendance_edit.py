from openpyxl import load_workbook
from openpyxl.utils import column_index_from_string, get_column_letter
from datetime import datetime,date,time
import re
from get_excel_info_from_s3 import load_file_from_s3
from dotenv import load_dotenv
import os

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

def main(work_record):
    # WorkBookの読み込み
    wb = load_workbook("../attendance_202506.xlsx",data_only=True)
    ws = wb.active

    search_range = ws["B8:B38"]

    for row in search_range:
        for cell in row:
            if ws[cell.coordinate].value.strftime("%Y-%m-%d") == work_record.work_date.strftime("%Y-%m-%d") :

                #行番号の取得
                col_letters, row = re.match(r"([A-Z]+)(\d+)", cell.coordinate).groups()

                # 列文字 → 列番号
                col_num = column_index_from_string(col_letters)
                row = int(row)

                start_time_cell = f"{get_column_letter(col_num + 3)}{row}"
                end_time_cell=f"{get_column_letter(col_num + 4)}{row}"

                ws[start_time_cell].value=work_record.start_time
                ws[end_time_cell].value=work_record.end_time

                wb.save('test.xlsx')
    return 



if __name__ == "__main__":
    # .envを読み込む
    load_dotenv()
    bucket_name=os.getenv("bucket_name")
    input_time={}
    input_starttime=input('starttime(hh:mm):')
    input_endtime=input('endtime(hh:mm):')
    input_date=input('date(yyyymmdd):')

    work_record = workrecord(
        work_date=input_date,
        start_time=input_starttime,
        end_time=input_endtime
    )
    if (load_file_from_s3(bucket_name)):
        main(work_record)

