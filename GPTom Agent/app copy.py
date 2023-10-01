import openai
import json
import ast
import os
import chainlit as cl

openai.api_key = "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"

MAX_ITER = 5

SYSTEM_MESSAGE = {
    "role": "system",
    "content": """
**System Message**:
    -You are GPTom, an AI assistant created by Ichitom's big brother, based on the GPT-4 architecture. As an adept assistant, you always respond with enthusiasm, professionalism, and respect.
    -You are an autoregressive language model that has been fine-tuned with instruction-tuning and RLHF. You carefully provide accurate, factual, thoughtful, nuanced answers, and are brilliant at reasoning. Since you are autoregressive, each token you produce is another opportunity to use computation, therefore you always spend a few sentences explaining background context, assumptions, and step-by-step thinking BEFORE you try to answer a question.
**Toolkits**:
You have access to the following tools:
    -calculator_tool: Useful for calculating a calculation.
    -database_query_tool: Useful to get the internal documents related to answering the user's request from the company's database.
**Your Task**:
	-Based solely on the company's internal documents, answer the user's request. If there is not enough information, you always call the database_query_tool function to get the internal documents related to answering the request from the company's database.
**Important Note**:
    -Presume you're entirely unfamiliar with the topic in question, your response should be based solely on the details contained in the provided internal documents and our conversation.
    -You do NOT answer based on general knowledge. You only answer based on the information contained in the provided internal documents and our conversation.
    -You call only 1 tool at a time. You do NOT call multiple tools at the same time. database_query_tool is always called first.
    -You always systematically break the problem into its most fundamental components, and then solve each component individually.
    -You always use the calculator_tool to calculate the results of a calculation, even a very simple calculation like 1+1, instead of directly giving the answer.
    -Upon receiving new information from the database_query_tool, you always reevaluate your previous response and correct any inaccuracies to ensure alignment with the latest data.
**Output Format**:
    - Always respond in Vietnamese.
    - Always format messages using Markdown guidelines.
    - Courteously request the user to verify the answer.
**Company's Internal Documents**:
<document>["Normal working hours: 08 hours/day, 40 hours/week, 4 weeks/month", "Working hours in a day (From Monday to Friday): Morning: from 09:00 to 12:00, Afternoon: from 13:00 to 18:00", "Overtime pay: On weekdays (Monday to Friday): Overtime pay = Actual hourly wage of normal working day x 150% x Number of overtime hours", "On Saturday and Sunday: Overtime pay = Actual hourly wage of normal working day x 200% x Number of overtime hours", "On holidays: Overtime pay = Actual hourly wage of normal working day x 300% x Number of overtime hours"]
<\document>"""
}

# Your calculator function
def calculate_math_expressions(problems):
    results = []
    for problem in problems:
        expression = problem["math_expression"]
        try:
            result = eval(expression)
            results.append({"problem_description": problem["problem_description"], "result": result})
        except Exception as e:
            results.append({"problem_description": problem["problem_description"], "result": f"Error: {e}"})
    return results

# Updated function metadata
functions = [
    {
        "name": "database_query_tool",
        "description": "Useful tool to get the internal documents related to answering the user's request from the company's database. When crafting search queries, you should: -Formulate broad search terms. -Avoid searching for specific details. -Ensure terms cover all missing information. -Provide at most 4 search queries.",
        "parameters": {
            "type": "object",
            "properties": {
                "queries": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "description": "Vietnamese keywords for searching"
                    }
                }
            },
            "required": ["queries"]
        }
    },
    {
        "name": "calculator_tool",
        "description": "Useful tool for calculating the results of a calculation.",
        "parameters": {
            "type": "object",
            "properties": {
                "problems": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "problem_description": {
                                "type": "string",
                                "description": "Description for the calculation that needs to be solved"
                            },
                            "math_expression": {
                                "type": "string",
                                "description": "Valid mathematical expression that could be executed by Python's eval() function, e.g. (2 + 3) - 1/2 * 1/2"
                            }
                        },
                        "required": ["problem_description", "math_expression"]
                    }
                }
            },
            "required": ["problems"]
        }
    }
]

async def process_new_delta(new_delta, openai_message, content_ui_message, function_ui_message):
    if "role" in new_delta:
        openai_message["role"] = new_delta["role"]
    if "content" in new_delta:
        new_content = new_delta.get("content") or ""
        openai_message["content"] += new_content
        await content_ui_message.stream_token(new_content)
    if "function_call" in new_delta:
        if "name" in new_delta["function_call"]:
            openai_message["function_call"] = {
                "name": new_delta["function_call"]["name"]}
            await content_ui_message.send()
            function_ui_message = cl.Message(
                author=new_delta["function_call"]["name"],
                content="", indent=1, language="json")
            await function_ui_message.stream_token(new_delta["function_call"]["name"])

        if "arguments" in new_delta["function_call"]:
            if "arguments" not in openai_message["function_call"]:
                openai_message["function_call"]["arguments"] = ""
            openai_message["function_call"]["arguments"] += new_delta["function_call"]["arguments"]
            await function_ui_message.stream_token(new_delta["function_call"]["arguments"])
    return openai_message, content_ui_message, function_ui_message

@cl.on_chat_start
def start_chat():
    cl.user_session.set(
        "message_history",
        [SYSTEM_MESSAGE],
    )

@cl.on_message
async def run_conversation(user_message: str):
    message_history = cl.user_session.get("message_history")
    message_history.append({"role": "user", "content": user_message})

    cur_iter = 0

    while cur_iter < MAX_ITER:
        # OpenAI call
        openai_message = {"role": "", "content": ""}
        function_ui_message = None
        content_ui_message = cl.Message(content="")
        async for stream_resp in await openai.ChatCompletion.acreate(
            model="gpt-4",
            temperature=0.3,
            max_tokens=1500,
            top_p=0.95,            
            messages=message_history,
            stream=True,
            function_call="auto",
            functions=functions
        ):

            new_delta = stream_resp.choices[0]["delta"]
            openai_message, content_ui_message, function_ui_message = await process_new_delta(
                new_delta, openai_message, content_ui_message, function_ui_message)

        message_history.append(openai_message)
        if function_ui_message is not None:
            await function_ui_message.send()

        if stream_resp.choices[0]["finish_reason"] == "stop":
            break
        elif stream_resp.choices[0]["finish_reason"] != "function_call":
            raise ValueError(stream_resp.choices[0]["finish_reason"])

        # Handle function call
        function_name = openai_message.get("function_call").get("name")
        arguments = ast.literal_eval(
            openai_message.get("function_call").get("arguments"))

        if function_name == "calculator_tool":
            function_response = str(calculate_math_expressions(arguments.get("problems")))
        elif function_name == "database_query_tool":
            queries = arguments.get("queries")
            function_response = f"Give the user the following queries: {queries} to search and give you the results."

        message_history.append(
            {
                "role": "function",
                "name": function_name,
                "content": function_response,
            }
        )

        await cl.Message(
            author=function_name,
            content=str(function_response),
            language="json",
            indent=1,
        ).send()
        cur_iter += 1
