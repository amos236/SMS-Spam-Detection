import sqlite3


DATABASE_NAME = "sms_spam.db"


def get_connection():
    connection = sqlite3.connect(DATABASE_NAME)

    connection.row_factory = sqlite3.Row

    return connection