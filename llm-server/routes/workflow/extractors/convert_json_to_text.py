import os
import logging
from langchain.schema import HumanMessage, SystemMessage

from integrations.custom_prompts.prompt_loader import load_prompts
from typing import Optional, Dict, Any, cast
from utils.get_chat_model import get_chat_model
from utils.chat_models import CHAT_MODELS
from utils.get_logger import CustomLogger
from flask_socketio import emit

openai_api_key = os.getenv("OPENAI_API_KEY")
logger = CustomLogger(module_name=__name__)


def convert_json_to_text(
    user_input: str,
    api_response: Dict[str, Any],
    api_request_data: Dict[str, Any],
    session_id: str,
    summary_prompt: str,
) -> str:
    chat = get_chat_model()
    system_message = SystemMessage(content=summary_prompt)

    messages = [
        system_message,
        HumanMessage(
            content="You'll receive user input and server responses obtained by making calls to various APIs. Your task is to summarize the api response that is an answer to the user input. Try to be concise and accurate, and also include references if present."
        ),
        HumanMessage(content=user_input),
        HumanMessage(
            content="Here is the response from the apis: {}".format(api_response)
        ),
    ]

    stream = chat.stream(messages)

    output = ""
    for chunk in stream:
        emit(session_id, chunk)
        output = output + str(chunk.content)

    logger.info(
        "Convert json to text",
        content=output,
        incident="convert_json_to_text",
        api_request_data=api_request_data,
    )

    return cast(str, output)
