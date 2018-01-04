from Crypto.Cipher import Blowfish
from Crypto import Random
from base64 import urlsafe_b64encode, urlsafe_b64decode


# References: http://stackoverflow.com/a/32311090
# http://pydoc.net/Python/pycrypto/2.6.1/Crypto.Cipher/

def encrypt(key, raw, algorithm=Blowfish, mode=2):
    """ Using a key, encrypt a raw string.

    :Parameters:
      key : a string
        The secret key to use in the symmetric cipher.
        Its length must be compatible with the algorithm being used.
      raw : a string
        The raw text that is to be encrypted.
        Its length will proportionally determine the length of the output in
        steps equal to the segment size used by the algorithm chosen.
    :Keywords:
      algorithm : a Crypto.Cipher module
        The choice of algorithm determines the required length of the `key`
        parameter, as well as the length and security of the resultant
        ciphertext.
        Compatible algorithms include AES, ARC2, Blowfish, CAST, DES, and DES3.
        Default is `Blowfish`.
      mode : an integer
        The chaining mode to use for encryption or decryption.
        Default is pycrypto's `MODE_CBC`, which may be indicated using `2`.

    :Return: a string """

    bs = algorithm.block_size
    padded = raw + (bs - len(raw) % bs) * chr(bs - len(raw) % bs)
    initialization_vector = Random.new().read(bs)
    cipher = algorithm.new(key, mode, initialization_vector)
    return initialization_vector + cipher.encrypt(padded)


def decrypt(key, ciphertext, algorithm=Blowfish, mode=2):
    """ Using a key string, decrypt an encoded string.

    :Parameters:
      key : a string
        The secret key used by the symmetric cipher.
      ciphertext : a string
        The ciphertext to be decrypted.
    :Keywords:
      algorithm : a Crypto.Cipher module
        The algorithm must match the one used to encrypt the `ciphertext`.
        Default is `Blowfish`.
      mode : an integer
        The chaining mode to use for encryption or decryption.
        Default is pycrypto's `MODE_CBC`, which may be indicated using `2`.

    :Return: a string """

    bs = algorithm.block_size
    initialization_vector = ciphertext[:bs]
    cipher = algorithm.new(key, mode, initialization_vector)
    padded = cipher.decrypt(ciphertext[bs:])
    unpadded = padded[:-ord(padded[len(padded)-1:])]
    return unpadded


def b64_encrypt(key, raw, **kwargs):
    """ Using a key string, encrypt a string and return the result encoded in
    URL-safe base 64 with no B64 padding characters. """
    return urlsafe_b64encode(encrypt(key, raw, **kwargs)).rstrip('=')


def b64_decrypt(key, ciphertext, **kwargs):
    """ Using a key string and a URL-safe base 64 ciphertext string with no B64
    padding characters, decrypt the ciphertext and return the result. """
    padding_needed = (-len(ciphertext) % 4)
    ciphertext = urlsafe_b64decode(ciphertext + '=' * padding_needed)
    return decrypt(key, ciphertext, **kwargs)
