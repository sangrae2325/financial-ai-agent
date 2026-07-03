from collectors.exchange_rate import fetch_exchange_rate
from validation.data_quality import validate_exchange_payload

data = fetch_exchange_rate()

validate_exchange_payload(data)

print(data["base_code"])
print(data["rates"]["KRW"])