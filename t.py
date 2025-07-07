import requests

# Hardcoded values from the provided images
url = "https://erp-new.go-globe.dev/api/leads"
auth_token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyIjoibGVhZHMiLCJuYW1lIjoibGVhZHMiLCJBUElfVElNRSI6MTczNjkzNzA2M30.6bf1TeZd1vEuA_qQydUMrPlO34Ft7faCFRWTm3n8OXY" # This token is incomplete from the image, please replace with the full valid token.

# Headers
headers = {
    "authtoken": auth_token,
    "Content-Type": "application/x-www-form-urlencoded" # Important for form-data
}

# Form data payload
data = {
    "name": "sss",
    "title": "destination",
    "phone": "0246954",
    "email": "afdfsd22@dssf.com"
}

try:
    # Make the POST request
    response = requests.post(url, headers=headers, data=data)

    # Check for successful response (status code 200)
    response.raise_for_status()

    # Print the response details
    print("Request successful!")
    print(f"Status Code: {response.status_code}")
    print("Response Body:")
    print(response.json())

except requests.exceptions.HTTPError as http_err:
    print(f"HTTP error occurred: {http_err}")
    print(f"Response content: {response.text}")
except Exception as err:
    print(f"An unexpected error occurred: {err}")
