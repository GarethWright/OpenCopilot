import json
import logging
from typing import Optional

from werkzeug.datastructures import Headers

from custom_types.bot_response import BotResponse
from custom_types.run_workflow_input import ChatContext
from entities.flow_entity import FlowDTO
from routes.flow.utils import run_actions
from utils.get_logger import CustomLogger

logger = CustomLogger(module_name=__name__)


async def run_flow(
        flow: FlowDTO,
        chat_context: ChatContext,
        app: Optional[str],
        bot_id: str,
) -> BotResponse:
    headers = chat_context.headers or Headers()

    result = ""
    error = None

    try:
        result = await run_actions(
            flow=flow,
            text=chat_context.text,
            headers=headers,
            app=app,
            bot_id=bot_id,
        )
    except Exception as e:
        payload_data = {
            "headers": dict(headers),
            "app": app,
        }

        logger.error("An exception occurred", payload=json.dumps(payload_data), error=str(e))

    output = BotResponse(text_response=result, errors=error)
    logging.info(
        "Workflow output %s", json.dumps(output, separators=(",", ":"))
    )
    return output
