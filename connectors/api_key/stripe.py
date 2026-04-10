import requests

class StripeConnector:

    BASE_URL = "https://api.stripe.com/v1"

    def __init__(self, api_key=None):
        self.api_key = api_key

    def get_auth_headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/x-www-form-urlencoded"
        }

    def list_customers(self, limit=10):
        headers = self.get_auth_headers()
        params = {"limit": limit}
        response = requests.get(f"{self.BASE_URL}/customers", headers=headers, params=params)
        return response.json()

    def list_invoices(self, limit=10):
        headers = self.get_auth_headers()
        params = {"limit": limit}
        response = requests.get(f"{self.BASE_URL}/invoices", headers=headers, params=params)
        return response.json()

    def list_charges(self, limit=10):
        headers = self.get_auth_headers()
        params = {"limit": limit}
        response = requests.get(f"{self.BASE_URL}/charges", headers=headers, params=params)
        return response.json()

    def list_products(self, limit=10):
        headers = self.get_auth_headers()
        params = {"limit": limit}
        response = requests.get(f"{self.BASE_URL}/products", headers=headers, params=params)
        return response.json()

    def create_customer(self, email, name=None):
        headers = self.get_auth_headers()
        data = {
            "email": email,
            "name": name or email
        }
        response = requests.post(f"{self.BASE_URL}/customers", headers=headers, data=data)
        return response.json()

    def get_balance(self):
        headers = self.get_auth_headers()
        response = requests.get(f"{self.BASE_URL}/balance", headers=headers)
        return response.json()

    def execute(self, action, params=None):
        params = params or {}
        if action == "list_customers":
            return self.list_customers(params.get("limit", 10))
        elif action == "list_invoices":
            return self.list_invoices(params.get("limit", 10))
        elif action == "list_charges":
            return self.list_charges(params.get("limit", 10))
        elif action == "list_products":
            return self.list_products(params.get("limit", 10))
        elif action == "create_customer":
            return self.create_customer(params.get("email"), params.get("name"))
        elif action == "get_balance":
            return self.get_balance()
        return {"error": "Unknown action"}