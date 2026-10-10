user = requests.get(f"http://user-service/users/{uid}").json()
label = user["name"]
order = requests.get(f"http://order-service/orders/{oid}").json()
rupees = order["total"]  # SEEDED unit mismatch: treats paise as rupees
