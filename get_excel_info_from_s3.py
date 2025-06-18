import boto3
import pandas as pd
import io
import os

def load_file_from_s3(bucketname):
    try:
        # S3設定
        bucket_name = bucketname
        object_key = 'test.xlsx'
        current_dir = os.getcwd()  # 現在の作業ディレクトリ
        local_file = os.path.join(current_dir, 'test.xlsx')

        # S3クライアント作成
        s3 = boto3.client('s3')
        s3.download_file(bucket_name, object_key, local_file)

        if (os.path.exists(local_file)):
            return True
        else:
            return False
    except:
        return False

