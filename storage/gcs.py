from google.cloud import storage
from app.config import PROJECT_ID, BUCKET_NAME

def upload_to_gcs(source_path: str, object_name: str) -> str:
    """
    로컬 파일을 GCS에 업로드한다.
    """
    client = storage.Client(project=PROJECT_ID)

    bucket = client.bucket(BUCKET_NAME)

    blob = bucket.blob(object_name)

    blob.upload_from_filename(source_path)

    gcs_uri = f"gs://{BUCKET_NAME}/{object_name}"
    
    print(f"[GCS] 업로드 완료 -> {gcs_uri}")

    return gcs_uri