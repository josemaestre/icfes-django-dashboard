import os
path = r'c:\proyectos\www\reback\reback\users\wompi_client.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

old_str = 'payload["payment_method"]["payment_source_id"] = payment_source_id'
new_str = 'payload["payment_source_id"] = payment_source_id\n                payload.pop("acceptance_token", None)\n                payload.pop("payment_method", None)'
text = text.replace(old_str, new_str)

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)
