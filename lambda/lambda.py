import json

import chdb


def handler(event, context):
    if "requestContext" in event:
        event = json.loads(event["body"])
    query = event["query"] if "query" in event else "SELECT version()"
    format = event["default_format"] if "default_format" in event else "JSONCompact"

    res = chdb.query(query, format).data()
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": str(res) if not isinstance(res, (dict, list)) else json.dumps(res),
    }
