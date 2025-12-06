from setuptools import setup

setup(
    name="trading-bot",
    version="1.0.0",
    install_requires=[
        "tinkoff-investments @ git+https://github.com/Tinkoff/invest-python.git@master",
        "flask==2.3.3",
        "schedule==1.2.0",
        "requests==2.31.0",
        "python-dotenv==1.0.0",
        "httpx==0.27.0",
        "aiohttp==3.9.3",
        "grpcio==1.62.1",
        "grpcio-tools==1.62.1",
        "protobuf==4.25.3"
    ],
    python_requires=">=3.10,<3.13",
)
