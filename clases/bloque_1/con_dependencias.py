#!/usr/bin/env python3
"""Script que usa una biblioteca externa."""

import requests

response = requests.get("https://httpbin.org/get")
print(f"Status: {response.status_code}")
print(f"Datos: {response.json()['origin']}")
