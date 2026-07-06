from collectors.exchange_rate import fetch_exchange_rate
from validation.data_quality import validate_exchange_payload
from storage.local import save_json


data = fetch_exchange_rate()

save_json(
    data,
    "data/exchange.json",
)

validate_exchange_payload(data)

print(data["base_code"])
print(data["rates"]["KRW"])