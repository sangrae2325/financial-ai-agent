from storage.gcs import upload_json
from collectors.exchange_rate import fetch_exchange_rate
from validation.data_quality import validate_exchange_payload
from storage.local import save_json


data = fetch_exchange_rate()

validate_exchange_payload(data)

file_path = save_json(
    data,
    "exchange",
)

gcs_uri = upload_json(
    file_path,
    "exchange",
)

print(gcs_uri)

print(data["base_code"])
print(data["rates"]["KRW"])




