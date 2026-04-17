from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
import hashlib
import sys


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
        print(len(message))
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

# message = '字' * 9
# print(sys.getsizeof(message))

# message = user1.enctypt_message(message, user2.get_public_key())

# message = user2.decrypt_message(message)

# print(message)

# a = bytes('字' * 91, encoding='UTF-8')

# print(len(a))
# print(list(a))


# for i in range(0, len(a), 180):
#     print(len(a[i:i + 180]))

# print(hashlib.sha256('12345678'.encode("utf-8")).hexdigest())

import pygame
pygame.init()
print(pygame.image.get_extended())