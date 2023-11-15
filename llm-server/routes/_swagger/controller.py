from flask import Flask, request, jsonify, Blueprint, request, Response

import json, yaml, re
from bson import ObjectId
import routes._swagger.service as swagger_service

from utils.db import Database
from qdrant_client import QdrantClient
from qdrant_client.http import models

import os

client = QdrantClient(url=os.getenv("QDRANT_URL", "http://qdrant:6333"))

db_instance = Database()
mongo = db_instance.get_db()
_swagger = Blueprint("_swagger", __name__)


@_swagger.route("/u/<swagger_url>", methods=["GET"])
def get_swagger_files(swagger_url: str) -> Response:
    # Validate and parse page and page_size query params
    try:
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 10))
        if page < 1 or page_size < 1:
            return jsonify({"message": "Invalid page or page_size"}), 400
    except ValueError:
        return jsonify({"message": "Invalid page or page_size"}), 400

    # Calculate document skip/limit
    skip = (page - 1) * page_size
    limit = page_size

    # Query for paginated docs
    try:
        files = [
            doc.update({"_id": str(doc["_id"])}) or doc
            for doc in mongo.swagger_files.find({"meta.swagger_url": swagger_url}, {})
            .skip(skip)
            .limit(limit)
        ]
    except Exception as e:
        return jsonify({"message": f"Database error: {str(e)}"}), 500

    # Get total docs count
    total = mongo.swagger_files.count_documents({"meta.swagger_url": swagger_url})

    # Prepare response data
    data = {"total": total, "page": page, "page_size": page_size, "files": files}

    return jsonify(data)


@_swagger.route("/get/b/<bot_id>", methods=["GET"])
def get_swagger_files_by_bot_id(bot_id: str) -> Response:
    swagger_file = mongo.swagger_files.find_one({"meta.bot_id": bot_id})
    if not swagger_file:
        return jsonify({"message": "Swagger file not found"}), 404
    swagger_file["_id"] = str(swagger_file["_id"])

    return jsonify(swagger_file)


@_swagger.route("/b/<id>", methods=["GET", "POST"])
def add_swagger_file(id) -> Response:
    result = swagger_service.add_swagger_file(request, id)
    return jsonify(result)


@_swagger.route("/init/b/<bot_id>", methods=["GET", "POST"])
def add_init_swagger_file(bot_id: str) -> Response:
    body = request.get_json()
    swagger_url = body["swagger_url"]
    client.create_collection(
        collection_name=bot_id,
        vectors_config=models.VectorParams(size=1536, distance=models.Distance.COSINE),
    )

    result = swagger_service.save_swaggerfile_to_mongo(swagger_url, bot_id)
    return jsonify(result)


@_swagger.route("/<_id>", methods=["GET"])
def get_swagger_file(_id: str) -> Response:
    # Validate _id
    if not ObjectId.is_valid(_id):
        return jsonify({"message": "Invalid _id format"}), 400

    file = mongo.swagger_files.find_one({"_id": ObjectId(_id)})
    if not file:
        return jsonify({"message": "Swagger file not found"}), 404

    file["_id"] = str(file["_id"])
    return jsonify(file)


@_swagger.route("/transform/<_id>", methods=["GET"])
def get_transformed_swagger_file(_id: str) -> Response:
    # Validate _id
    if not ObjectId.is_valid(_id):
        return jsonify({"message": "Invalid _id format"}), 400

    swagger_json = mongo.swagger_files.aggregate(
        [
            {"$match": {"_id": ObjectId(_id)}},
            {"$project": {"paths": 1}},
            {
                "$project": {
                    "methods": {
                        "$reduce": {
                            "input": {"$objectToArray": "$paths"},
                            "initialValue": [],
                            "in": {
                                "$concatArrays": [
                                    "$$value",
                                    {
                                        "$map": {
                                            "input": {"$objectToArray": "$$this.v"},
                                            "as": "path",
                                            "in": {
                                                "$mergeObjects": [
                                                    "$$path.v",
                                                    {
                                                        "method": "$$path.k",
                                                        "path": "$$this.k",
                                                    },
                                                ]
                                            },
                                        }
                                    },
                                ]
                            },
                        }
                    }
                }
            },
            {
                "$project": {
                    "methods.requestBody": 0,
                    "methods.responses": 0,
                    "methods.security": 0,
                }
            },
        ]
    )

    swagger_json = [doc.update({"_id": str(doc["_id"])}) or doc for doc in swagger_json]

    return jsonify(list(swagger_json))


@_swagger.route("/<_id>", methods=["PUT"])
def update_swagger_file(_id: str) -> Response:
    if not ObjectId.is_valid(_id):
        return jsonify({"message": "Invalid _id format"}), 400

    data = request.get_json()
    result = mongo.swagger_files.update_one({"_id": ObjectId(_id)}, {"$set": data})
    if result.modified_count == 1:
        return jsonify({"message": "Swagger file updated successfully"})
    return jsonify({"message": "Swagger file not found"}), 404


@_swagger.route("/<_id>", methods=["DELETE"])
def delete_swagger_file(_id: str) -> Response:
    if not ObjectId.is_valid(_id):
        return jsonify({"message": "Invalid _id format"}), 400

    result = mongo.swagger_files.delete_one({"_id": ObjectId(_id)})
    if result.deleted_count == 1:
        return jsonify({"message": "Swagger file deleted successfully"})
    return jsonify({"message": "Swagger file not found"}), 404
