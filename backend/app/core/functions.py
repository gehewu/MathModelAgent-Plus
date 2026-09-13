"""工具函数定义模块，为各 Agent 提供可用的工具 schema。"""

# ---- OpenAI 格式（Chat Completions + Responses 共用） ----

coder_tools = [
    {
        "type": "function",
        "function": {
            "name": "execute_code",
            "description": "This function allows you to execute Python code and retrieve the terminal output. If the code "
            "generates image output, the function will return the text '[image]'. The code is sent to a "
            "Jupyter kernel for execution. The kernel will remain active after execution, retaining all "
            "variables in memory."
            "You cannot show rich outputs like plots or images, but you can store them in the working directory and point the user to them. ",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "The code text"}
                },
                "required": ["code"],
                "additionalProperties": False,
            },
        },
    },
]

writer_tools = [
    {
        "type": "function",
        "function": {
            "name": "search_papers",
            "description": "Search for papers using a query string.",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The query string"}
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
]

# ---- Web Search 工具（启用时由 CoderAgent 拼接到 tools） ----

web_search_tools = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the internet using Tavily to get real-world data. "
            "Use this when you need current facts, statistics, or information not "
            "available in the dataset. Returns titles, URLs, and content snippets.",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query string",
                    }
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
]

web_search_tools_anthropic = [
    {
        "name": "web_search",
        "description": "Search the internet using Tavily to get real-world data. "
        "Use this when you need current facts, statistics, or information not "
        "available in the dataset. Returns titles, URLs, and content snippets.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query string"}
            },
            "required": ["query"],
        },
    },
]

# ---- Anthropic 格式 ----

coder_tools_anthropic = [
    {
        "name": "execute_code",
        "description": "This function allows you to execute Python code and retrieve the terminal output. If the code "
        "generates image output, the function will return the text '[image]'. The code is sent to a "
        "Jupyter kernel for execution. The kernel will remain active after execution, retaining all "
        "variables in memory."
        "You cannot show rich outputs like plots or images, but you can store them in the working directory and point the user to them. ",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "The code text"}
            },
            "required": ["code"],
        },
    },
]

writer_tools_anthropic = [
    {
        "name": "search_papers",
        "description": "Search for papers using a query string.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The query string"}
            },
            "required": ["query"],
        },
    },
]
