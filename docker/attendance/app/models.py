from datetime import datetime, timedelta, date, time
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


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

        if self.work_style == "休み":
            self.start_time = None
            self.end_time = None
        else:
            self.start_time = self.ensure_time(start_time) if start_time else time(9, 0)
            self.end_time = self.ensure_time(end_time) if end_time else time(17, 30)
                
        if work_style == '休み':
            self.break_time = timedelta()
            self.work_time = None
        elif break_time:
            t = datetime.strptime(break_time, "%H:%M")
            self.break_time = timedelta(hours=t.hour, minutes=t.minute)
        else:
            self.break_time = self.calculate_break_minutes(self.start_time, self.end_time)

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
            if self.start_time is None or self.end_time is None:
                logger.warning("start_time or end_time is None in calculate_work_time")
                return None
            start_dt = datetime.combine(date.today(), self.start_time)
            end_dt = datetime.combine(date.today(), self.end_time)
            if end_dt < start_dt:
                end_dt += timedelta(days=1)
            return end_dt - start_dt - self.break_time
        except Exception as e:
            logger.error(f"Work time calculation error: {e}")
            return None
        
    def ensure_time(self, t):
        try:
            if isinstance(t, time):
                return t.replace(second=0, microsecond=0)
            if isinstance(t, str) and t.strip():
                return datetime.strptime(t.strip(), "%H:%M").time().replace(second=0, microsecond=0)
        except Exception as e:
            logger.warning(f"Invalid time format: {t} ({e})")
        return time(0, 0)  # デフォルトで 00:00 にする or None ではなく例外を防ぐ

    def overlap_minutes(self, start1, end1, start2, end2):
        latest_start = max(start1, start2)
        earliest_end = min(end1, end2)
        delta = (earliest_end - latest_start).total_seconds()
        return max(0, delta / 60)

    def calculate_break_minutes(self, start_time_obj, end_time_obj):
        if start_time_obj is None or end_time_obj is None:
            logger.warning("start_time or end_time is None in calculate_break_minutes")
            return timedelta()

        base_date = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
        start_time = datetime.combine(base_date, start_time_obj)
        end_time = datetime.combine(base_date, end_time_obj)
        if end_time < start_time:
            end_time += timedelta(days=1)

        total_break_minutes = 0
        for b_start, b_end in self.bread_periods():
            b_start_dt = datetime.combine(base_date, b_start)
            b_end_dt = datetime.combine(base_date, b_end)

            # ここが重要：break時間が退勤時間よりも後になっているときの補正を明確化
            if b_end_dt < b_start_dt:
                b_end_dt += timedelta(days=1)

            # 開始・終了時間にかかる break を集計
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


def Input_Check(work_record):
    if work_record.start_time and work_record.end_time:
        if work_record.start_time > work_record.end_time:
            return 'end_time before start_time'

def get_weekday_abbr(dt: datetime) -> str:
    return dt.strftime("%a")