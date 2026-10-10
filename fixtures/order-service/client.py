user = requests.get(f"http://user-service/users/{uid}").json()
greeting = "Hi " + user["name"]  # consumer still assumes "name"
