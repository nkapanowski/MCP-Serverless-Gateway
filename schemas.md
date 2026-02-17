# Global Request Schema
{
  "tool": "string",
  "request_id": "string",
  "parameters": {}
}


# Global Success Repsonse Schema
{
  "status": "success",
  "request_id": "string",
  "data": {},
  "execution_time_ms": 0
}

# Global Error Response Schema
{
  "status": "error",
  "request_id": "string",
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable explanation"
  },
  "execution_time_ms": 0
}

# Search Tool Schema (Request)
{
  "tool": "search",
  "request_id": "string",
  "parameters": {
    "query": "string"
  }
}

# Search Tool Schema (Success Response)
{
  "status": "success",
  "request_id": "string",
  "data": {
    "results": ["string"]
  },
  "execution_time_ms": 0
}


# File Tool Schema (Request)
{
  "tool": "file_read",
  "request_id": "string",
  "parameters": {
    "filename": "string"
  }
}

# File Tool Schema (Succes Response)
{
  "status": "success",
  "request_id": "string",
  "data": {
    "content": "string"
  },
  "execution_time_ms": 0
}
