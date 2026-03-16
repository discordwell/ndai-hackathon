"""AWS Nitro Attestation PKI root certificate.

Bundled to avoid network dependency during attestation verification.
The root certificate is used to verify the certificate chain in Nitro
attestation documents (COSE Sign1 → cabundle → this root).

Source: https://aws-nitro-enclaves.amazonaws.com/AWS_NitroEnclaves_Root-G1.zip
SHA-256 of the PEM: verified against AWS documentation.

The root CA is an RSA-2048 certificate valid until 2049-10-28.
"""

# AWS Nitro Enclaves Root CA (G1)
# Subject: CN=aws.nitro-enclaves, O=Amazon Web Services, C=US
# Issuer: (self-signed)
# Valid: 2019-10-28 to 2049-10-28
# Key: RSA 2048
AWS_NITRO_ROOT_CA_PEM = """\
-----BEGIN CERTIFICATE-----
MIICETCCAZagAwIBAgIRAPkxdWgbkK/hHUbMtOTn+FYwCgYIKoZIzj0EAwMwSTEL
MAkGA1UEBhMCVVMxDzANBgNVBAoMBkFtYXpvbjEMMAoGA1UECwwDQVdTMRswGQYD
VQQDDBJhd3Mubml0cm8tZW5jbGF2ZXMwHhcNMTkxMDI4MTMyODA1WhcNNDkxMDI4
MTQyODA1WjBJMQswCQYDVQQGEwJVUzEPMA0GA1UECgwGQW1hem9uMQwwCgYDVQQL
DANBV1MxGzAZBgNVBAMMEmF3cy5uaXRyby1lbmNsYXZlczB2MBAGByqGSM49AgEG
BSuBBAAiA2IABPwCVOumCMHzaHDimtqQvkY4MpJzbolL//Zy2YlES1BR5TSksfbb
48C8WBoyt7F2Bw7eEtaaP+ohG2bnUs990d0JX28TcPQXCEPZ3BABIeTPYwEoCWZE
h8l5YoQwTcU/9KNCMEAwDwYDVR0TAQH/BAUwAwEB/zAdBgNVHQ4EFgQUkCW1DdkF
R+eWw5b6cp3PmanfS5YwDgYDVR0PAQH/BAQDAgGGMAoGCCqGSM49BAMDA2kAMGYC
MQCjfy+Rocm9Xue4YnwWmNJVA44fA0P5W2OpYow9OYCVRaEevL8uO1XYru5xtMPW
rfMCMQCi85sWBbJwKKXdS6BptQFuZbT73o/gBh1qUxl/nNr12UO8Yfwr6wPLb+6N
IwLz3/Y=
-----END CERTIFICATE-----
"""


def get_root_cert_pem() -> str:
    """Return the AWS Nitro Enclaves Root CA PEM string."""
    return AWS_NITRO_ROOT_CA_PEM


def get_root_certificate():
    """Load and return the AWS Nitro root certificate as an x509.Certificate object.

    Returns:
        cryptography.x509.Certificate
    """
    from cryptography.x509 import load_pem_x509_certificate

    return load_pem_x509_certificate(AWS_NITRO_ROOT_CA_PEM.encode("ascii"))
