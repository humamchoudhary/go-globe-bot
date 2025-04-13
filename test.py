from py_vapid import Vapid01
import base64

vapid = Vapid01()
vapid.generate_keys()

# Export keys in the correct format
private_key = vapid.private_key
public_key = base64.urlsafe_b64encode(vapid.public_key.public_bytes(
    encoding=1,  # PEM
    format=1  # SubjectPublicKeyInfo
)).decode('utf-8')

print(f'PRIVATE KEY: {private_key}')
print(f'PUBLIC KEY: {public_key}')
