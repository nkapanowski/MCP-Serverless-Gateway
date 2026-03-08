import json
import re;
import hashlib;
import time;
TOOLS = {}
def wordDictionary(sentence):
    newSentence = re.sub(r"[^\w\s]", "", sentence.lower())
    words = newSentence.split(" ");
    wordDict={};
    for word in words:
        if word in wordDict:
            wordDict[word]=wordDict[word]+1;
        else:
            wordDict[word]=1;
    return wordDict;
def sortedWordDictionary(sentence,n=5):
    wordDict = wordDictionary(sentence);
    return sorted(wordDict.items(), key=lambda x: x[1], reverse=True)[:n]
def hashThis(thing):
    hash_raw = hashlib.sha256(thing.encode())
    hash_hexidecimal = hash_raw.hexdigest();
    return hash_hexidecimal;
def add(a,b):
    return a+b;
def helloWorld():
    return "Hello world!!!"
def getTimeStampOfService():
    return int(time.time());
def tool(name, description, schema):
    def decorator(func):
        TOOLS[name] = {
            "func": func,
            "description": description,
            "schema": schema
        }
        return func
    return decorator


def jsonrpc_response(id_, result=None, error=None):
    body = {"jsonrpc": "2.0", "id": id_}
    if error:
        body["error"] = error
    else:
        body["result"] = result

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body)
    }

@tool(
    name="wordDictionary",
    description="Returns a dictionary of word counts for a given sentence",
    schema={
        "type": "object",
        "properties": {
            "sentence": {"type": "string"}
        },
        "required": ["sentence"]
    }
)
def wordDictionary_tool(args):
    return wordDictionary(args["sentence"])


@tool(
    name="sortedWordDictionary",
    description="Returns the top N most frequent words from a sentence",
    schema={
        "type": "object",
        "properties": {
            "sentence": {"type": "string"},
            "n": {"type": "integer", "default": 5}
        },
        "required": ["sentence"]
    }
)
def sortedWordDictionary_tool(args):
    n = args.get("n", 5)
    return sortedWordDictionary(args["sentence"], n)


@tool(
    name="hashThis",
    description="Returns the SHA-256 hash of a string",
    schema={
        "type": "object",
        "properties": {
            "thing": {"type": "string"}
        },
        "required": ["thing"]
    }
)
def hashThis_tool(args):
    return hashThis(args["thing"])


@tool(
    name="add",
    description="Adds two numbers",
    schema={
        "type": "object",
        "properties": {
            "a": {"type": "number"},
            "b": {"type": "number"}
        },
        "required": ["a", "b"]
    }
)
def add_tool(args):
    return add(args["a"], args["b"])


@tool(
    name="helloWorld",
    description="Returns a static hello message",
    schema={"type": "object", "properties": {}}
)
def helloWorld_tool(args):
    return helloWorld()


@tool(
    name="getTimeStampOfService",
    description="Returns the current Unix timestamp",
    schema={"type": "object", "properties": {}}
)
def getTimeStampOfService_tool(args):
    return getTimeStampOfService()
# Example tool
@tool(
    name="hello",
    description="Return greeting",
    schema={
        "type": "object",
        "properties": {
            "name": {"type": "string"}
        }
    }
)
def hello_tool(args):
    name = args.get("name", "world")
    return f"Hello there {name}"
@tool(name="goodbye", description="Say goodbye", schema={"type":"object","properties":{"name":{"type":"string"}}})
def goodbye_tool(args):
    return f"Never gonna give you up {args.get('name','world')}"

def list_tools():
    return {
        "tools": [
            {
                "name": name,
                "description": tool["description"],
                "inputSchema": tool["schema"]
            }
            for name, tool in TOOLS.items()
        ]
    }


def call_tool(name, arguments):
    if name not in TOOLS:
        raise Exception("Tool not found")

    result = TOOLS[name]["func"](arguments)

    return {
        "content": [
            {
                "type": "text",
                "text": str(result)
            }
        ]
    }


def lambda_handler(event, context):
    body = event.get("body") or "{}"
    
    try:
        req = json.loads(body)
    except Exception:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": "Parse error"
                }
            })
        }

    req_id = req.get("id")
    method = req.get("method")

    if method == "initialize":
        result = {
            "protocolVersion": "2024-11-05",
            "serverInfo": {
                "name": "lambda-mcp",
                "version": "1.0"
            },
            "capabilities": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {
                    "name": "lambda-mcp",
                    "version": "1.0"
                }
            }
        }
    elif method == "tools/list":
        result = list_tools();
    elif method == "tools/call":
        params = req.get("params", {})
        tool_name = params.get("name")            # tool name is in params.name
        arguments = params.get("arguments", {})   # tool args

        try:
            result = call_tool(tool_name, arguments)
        except Exception:
            return jsonrpc_response(req_id, error={"code": -32601, "message": "Tool not found"})
    else:
        # Return JSON-RPC compliant error
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": "Method not found"}
            })
        }

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"jsonrpc":"2.0","id":req_id,"result":result})
    }
