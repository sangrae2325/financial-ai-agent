from storage.gcs import upload_json
from collectors.exchange_rate import fetch_exchange_rate
from validation.data_quality import validate_exchange_payload
from storage.local import save_json


data = fetch_exchange_rate()

save_json(
    data,
    "data/exchange.json",
)

gcs_uri = upload_json(

    "data/exchange.json"

)

print(gcs_uri)
validate_exchange_payload(data)

print(data["base_code"])
print(data["rates"]["KRW"])