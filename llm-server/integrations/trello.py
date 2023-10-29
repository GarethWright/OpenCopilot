from typing import Dict, Any, Optional
import requests
from integrations.database import Database

db_instance = Database()
mongo = db_instance.get_db()
import time

def get_state(
    headers: Dict[str, Any], selected_board_id: Optional[str] = None
) -> Dict[str, Any]:
    state: Dict[str, Any] = {
        "appId": "trello",
        "appName": "Trello",
        "description": "Given below is an array of objects with boards, lists, and cards entities. You will find the boardId, boardName, listId, listName, cardId, and cardName.",
        "entities": {
            "data": [],
        },
    }

    # Step 1: Get the list of boards
    boards_endpoint = "https://api.trello.com/1/members/me?boards=open"
    response = requests.get(boards_endpoint, headers=headers)
    boards_data = response.json()

    for board in boards_data["boards"]:
        board_id = board["id"]
        board_name = board["name"]

        # Step 2: Get the lists for the current board
        if not selected_board_id or selected_board_id == board_id:
            lists_endpoint = f"https://api.trello.com/1/boards/{board_id}/lists"
            response = requests.get(lists_endpoint, headers=headers)
            lists_data = response.json()

            for l in lists_data:
                list_id = l["id"]
                list_name = l["name"]

                # Step 3: Get the cards for the current list
                cards_endpoint = f"https://api.trello.com/1/lists/{list_id}/cards"
                response = requests.get(cards_endpoint, headers=headers)
                cards_data = response.json()

                for card in cards_data:
                    card_id = card["id"]
                    card_name = card["name"]

                    # Append the data to the state's "entities" dictionary
                    state["entities"]["data"].append(
                        {
                            "boardId": board_id,
                            "boardName": board_name,
                            "listId": list_id,
                            "listName": list_name,
                            "cardId": card_id,
                            "cardName": card_name,
                        }
                    )

    return {"state": state["entities"]["data"]}


def process_state(headers: Dict[str, Any], selected_board_id: Optional[str] = None) -> Dict[str, Any]:
    # Get current timestamp
    now = time.time()

    # Try to find cached data from MongoDB
    cache = mongo.app_cache.find_one({"app": "trello"}, {"_id": 0})

    # Check if cache exists and is less than 2 minutes old
    if cache and now - cache["timestamp"] < 600:
        print("Returning cached data")
        return cache

    # Update cache object
    cache = get_state(headers, selected_board_id)

    # Insert into MongoDB
    mongo.app_cache.replace_one({"app": "slack"}, cache, upsert=True)

    return cache
