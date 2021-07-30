import os

uri = "postgres://aqsobsnembmsoq:169e3ffd2dc95de7eec64e5ece8d0fc45e3f73d014267114519261f20c3dee6a@ec2-3-226-134-153.compute-1.amazonaws.com:5432/de08ukqjjcfmcp"
if uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)

class Config(object):
    SQLALCHEMY_TRACK_MODIFICATIONS = True
    SECRET_KEY = "169e3ffd2dc95de7eec64e5ece8d0fc45e3f73d014267114519261f20c3dee6a"
    SQLALCHEMY_DATABASE_URI = uri