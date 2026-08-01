import json

def json_format(text:dict):
    return json.dumps(text, indent=4,ensure_ascii=False)

