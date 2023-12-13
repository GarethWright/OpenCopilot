from typing import cast

from flask import jsonify, Blueprint, request, Response, abort, Request
from routes.analytics.analytics_service import upsert_analytics_record
from routes.chat.chat_dto import ChatInput
from utils.get_logger import CustomLogger
from utils.llm_consts import X_App_Name
from utils.sqlalchemy_objs_to_json_array import sqlalchemy_objs_to_json_array
from models.repository.chat_history_repo import (
    get_all_chat_history_by_session_id,
    get_unique_sessions_with_first_message_by_bot_id,
    create_chat_history,
)
from models.repository.copilot_repo import find_one_or_fail_by_token
from utils.db import Database
from .. import root_service
from typing import Optional
from flask_socketio import emit

db_instance = Database()
mongo = db_instance.get_db()
logger = CustomLogger(module_name=__name__)

chat_workflow = Blueprint("chat", __name__)


def get_validated_data(request: Request) -> Optional[dict]:
    data = request.get_json()
    if not data:
        return None

    required_keys = {"app", "system_prompt", "summarization_prompt"}

    if not required_keys.issubset(data.keys()):
        print(
            f"Missing required keys in request: {required_keys.difference(data.keys())}"
        )
        return None

    return data


@chat_workflow.route("/sessions/<session_id>/chats", methods=["GET"])
def get_session_chats(session_id: str) -> Response:
    limit = int(request.args.get("limit", 20))
    offset = int(request.args.get("offset", 0))

    chats = get_all_chat_history_by_session_id(session_id, limit, offset)

    chats_filtered = []

    for chat in chats:
        chats_filtered.append(
            {
                "chatbot_id": chat.chatbot_id,
                "created_at": chat.created_at,
                "from_user": chat.from_user,
                "id": chat.id,
                "message": chat.message,
                "session_id": chat.session_id,
            }
        )

    return jsonify(chats_filtered)


@chat_workflow.route("/b/<bot_id>/chat_sessions", methods=["GET"])
def get_chat_sessions(bot_id: str) -> list[dict[str, object]]:
    limit = cast(int, request.args.get("limit", 20))
    offset = cast(int, request.args.get("offset", 0))
    chat_history_sessions = get_unique_sessions_with_first_message_by_bot_id(
        bot_id, limit, offset
    )

    return chat_history_sessions


@chat_workflow.route("/init", methods=["GET"])
def init_chat():
    bot_token = request.headers.get("X-Bot-Token")
    session_id = request.headers.get("X-Session-Id")

    history = []
    if session_id:
        chats = get_all_chat_history_by_session_id(session_id, 200, 0)
        history = sqlalchemy_objs_to_json_array(chats) or []

    if not bot_token:
        return (
            jsonify(
                {
                    "type": "text",
                    "response": {"text": "Could not find bot token"},
                }
            ),
            404,
        )

    bot = find_one_or_fail_by_token(bot_token)
    # Replace 'faq' and 'initialQuestions' with actual logic or data as needed.
    return jsonify(
        {
            "bot_name": bot.name,
            "logo": "logo",
            "faq": [],  # Replace with actual FAQ data
            "initial_questions": [],  # Replace with actual initial questions
            "history": history,
        }
    )


async def send_chat(json_data):
    logger.info("Received calls from socketio")
    input_data = ChatInput(**json_data)
    message = input_data.content
    session_id = input_data.session_id
    bot_token = input_data.token
    
    headers_from_json = input_data.headers


    if not message or len(message) > 255:
        emit(session_id, "Content length must be smaller than 255")

    bot = find_one_or_fail_by_token(bot_token)

    app_name = headers_from_json.pop(X_App_Name, None)

    swagger_url = bot.swagger_url

    base_prompt = bot.prompt_message
    server_base_url = request.form.get("server_base_url", "")

    if not bot:
        emit(
            session_id,
            {
                "type": "text",
                "response": {
                    "text": "I'm unable to help you at the moment, please try again later. **code: b404**"
                },
            },
        )

    try:
        response_data = await root_service.handle_request(
            text=message,
            swagger_url=str(swagger_url),
            session_id=session_id,
            base_prompt=str(base_prompt),
            bot_id=str(bot.id),
            headers=headers_from_json,
            server_base_url=server_base_url,
            app=app_name,
            summary_prompt=str(bot.summary_prompt),
        )

        if response_data["response"]:
            upsert_analytics_record(
                chatbot_id=str(bot.id), successful_operations=1, total_operations=1
            )
            create_chat_history(str(bot.id), session_id, True, message)
            create_chat_history(
                str(bot.id),
                session_id,
                False,
                response_data["response"] or response_data["error"] or "",
            )
        elif response_data["error"]:
            upsert_analytics_record(
                chatbot_id=str(bot.id),
                successful_operations=0,
                total_operations=1,
                logs=response_data["error"],
            )

        return {"type": "text", "response": {"text": response_data["response"]}}

    except Exception as e:
        logger.error("An exception occurred", incident="chat/send", error=str(e))

        emit(
            session_id,
            {
                "type": "text",
                "response": {
                    "text": f"I'm unable to help you at the moment, please try again later. **code: b500**\n```{e}```"
                },
            },
        ),
