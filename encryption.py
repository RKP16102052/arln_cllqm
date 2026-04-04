from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes


class User:
    def __init__(self):
        self.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )

        public_key = self.private_key.public_key()

        pem_public_key = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

        self.public_key = serialization.load_pem_public_key(pem_public_key)

    def get_public_key(self):
        return self.public_key

    def enctypt_message(self, message, public_key):
        message = bytes(message, encoding='UTF-8')
        message = public_key.encrypt(
            message,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )

        return message

    def decrypt_message(self, message):
        message = self.private_key.decrypt(
            message,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )

        message = message.decode()

        return message


# user1 = User()
# user2 = User()

# # Первый пользователь отправляет второму.
# message = 'Привет!!'

# message = user1.enctypt_message(message, user2.get_public_key())

# message = user2.decrypt_message(message)

# print(message)


# with open('/home/maksmesh/.local/share/arlene_m/keys/82c40eb1b194459ba99b5feeb13140ef', 'rb') as file:
#     data = file.read()

# private_key = serialization.load_pem_private_key(data, None)

# public_key = '''-----BEGIN PUBLIC KEY-----
# MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAj2AAefgLoEuJwcX8ZvMH
# f2I5cvZU8HLZzsK4ghAgIdaGqY+mk8FVq7y4FMPI4G2gyMcnUqRhazv2VJ4KiuZu
# /pRClP0HJIOTH60u+M90jIyq56QaJVjds+ON5OtQxZam+1vGgILD35CAi0XjGU+M
# 7bJ7OPjjBFOtsb0eQisabOHmf/dJWBd5wHjw+20jB9jAb1kXueYZaZSAKTdxQhcA
# AlyjlMT2Pj6JtFaPMI8TF7K2SfZLQodBUQ6AP2zRmWnB4dxgo6jK1VWgkAE0GfdX
# W24eUYw9p36zEToB4O5/gitQXKXq3UIlwdUM3Qaau2KH8pQVcWIvAMUxMY1m9lxQ
# /QIDAQAB
# -----END PUBLIC KEY-----
# '''

# message = bytes('АААА!', encoding='UTF-8')
# public_key = serialization.load_pem_public_key(bytes(public_key, 'UTF-8'))

# message = public_key.encrypt(
#     message,
#     padding.OAEP(
#         mgf=padding.MGF1(algorithm=hashes.SHA256()),
#         algorithm=hashes.SHA256(),
#         label=None
#     )
# )

# message = private_key.decrypt(
#     message,
#     padding.OAEP(
#         mgf=padding.MGF1(algorithm=hashes.SHA256()),
#         algorithm=hashes.SHA256(),
#         label=None
#     )
# )

# print(message.decode())

print(list({'a': 1}.keys()))