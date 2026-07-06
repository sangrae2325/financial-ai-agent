"""
Google Cloud Storage 업로드 모듈

기능
- 로컬 JSON 파일 업로드
"""
from pathlib import Path
from google.cloud import storage
from app.config import PROJECT_ID, BUCKET_NAME

def upload_json(file_path: str) -> str:
    """
    로컬 JSON 파일을 GCS에 업로드한다.

    Args:
        file_path: 업로드할 파일 경로

    Returns:
        업로드된 GCS URI

    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"{path} 파일이 존재하지 않습니다.")

    client = storage.Client(project=PROJECT_ID)
    bucket = client.bucket(BUCKET_NAME)
    object_name = f"exchange/{path.name}"
    blob = bucket.blob(object_name)
    blob.upload_from_filename(str(path))
    gcs_uri = f"gs://{BUCKET_NAME}/{object_name}"
    
    print(f"GCS Upload Success : {gcs_uri}")

    return gcs_uri