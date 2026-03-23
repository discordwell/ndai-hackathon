from setuptools import setup

setup(
    name="ndai-seal",
    version="0.1.0",
    description="Verify NDAI enclave attestation and encrypt exploits for sealed submission",
    py_modules=["ndai_seal"],
    install_requires=[
        "cryptography>=41.0",
        "httpx>=0.25",
        "cbor2>=5.5",
        "click>=8.0",
    ],
    entry_points={
        "console_scripts": [
            "ndai-seal=ndai_seal:cli",
        ],
    },
    python_requires=">=3.10",
)
