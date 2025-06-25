import boto3
import io
import os

def load_file_from_s3(bucketname):
    try:
        # S3設定
        bucket_name = bucketname
        object_key = 'attendance_202506.xlsx'
        current_dir = os.getcwd()  # 現在の作業ディレクトリ
        local_file = os.path.join(current_dir, 'test.xlsx')

        # S3クライアント作成
        s3 = boto3.client('s3')
        # 1️⃣ S3からファイルをダウンロード（メモリ上）
        response = s3.get_object(Bucket=bucket_name, Key=object_key)
        excel_data = response['Body'].read()

        return excel_data
    except:
        return False

