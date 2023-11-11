use crate::{AppState, schemas::chatbot::{ChatbotCreateRequest, FilterOptions}, models::chatbot::Chatbot};


use actix_web::{delete, get, post, web, HttpResponse, Responder};
use serde_json::json;


#[get("/healthchecker")]
async fn health_checker_handler() -> impl Responder {
    const MESSAGE: &str = "Build Simple CRUD API with Rust, SQLX, MySQL, and Actix Web";

    HttpResponse::Ok().json(json!({"status": "success","message": MESSAGE}))
}

#[post("/chatbot")]
pub async fn create_chatbot_handler(
    body: web::Json<ChatbotCreateRequest>,
    data: web::Data<AppState>,
) -> HttpResponse {
    let query_result =
        sqlx::query(r#"INSERT INTO chatbots (name,token,website,status) VALUES (?, ?, ?, ?)"#)
            .bind(body.name.clone())
            .bind(body.token.clone())
            .bind(body.website.clone())
            .bind(body.status.clone())
            .execute(&data.db)
            .await
            .map_err(|err: sqlx::Error| err.to_string());

    if let Err(err) = query_result {
            if err.contains("Duplicate entry") {
                return HttpResponse::BadRequest().json(
                serde_json::json!({"status": "fail","message": "chatbot with that title already exists"}),
            );
        }

        return HttpResponse::InternalServerError()
            .json(serde_json::json!({"status": "error","message": format!("{:?}", err)}));
    }

    HttpResponse::Ok().finish()
}

#[get("/chatbot/{id}")]
async fn get_chatbot_handler(
    path: web::Path<String>,
    data: web::Data<AppState>,
) -> HttpResponse {
    let chatbot_id = path.into_inner().to_string();
    let query_result = sqlx::query_as!(Chatbot, r#"SELECT * FROM chatbots WHERE id = ?"#, chatbot_id)
        .fetch_one(&data.db)
        .await;

    HttpResponse::Ok().json(query_result.unwrap())
}

#[get("/chatbots")]
pub async fn list_chatbot_handler(
    opts: web::Query<FilterOptions>,
    data: web::Data<AppState>,
) -> impl Responder {
    let limit = opts.limit.unwrap_or(10);
    let offset = (opts.page.unwrap_or(1) - 1) * limit;

    let chatbots: Vec<Chatbot> = sqlx::query_as!(
        Chatbot,
        r#"SELECT * FROM chatbots ORDER by id LIMIT ? OFFSET ?"#,
        limit as i32,
        offset as i32
    )
    .fetch_all(&data.db)
    .await
    .unwrap();


    let json_response = serde_json::json!({
        "status": "success",
        "chatbots": chatbots
    });
    HttpResponse::Ok().json(json_response)
}


#[delete("/chatbots/{id}")]
async fn delete_chatbot_handler(
    path: web::Path<String>,
    data: web::Data<AppState>,
) -> impl Responder {
    let chatbot_id = path.into_inner().to_string();
    let query_result = sqlx::query_as!(Chatbot, r#"DELETE FROM chatbots WHERE id = ?"#, chatbot_id)
        .execute(&data.db)
        .await;

    match query_result {
        Ok(result) => {
            if result.rows_affected() == 0 {
                let message = format!("chatbot with ID: {} not found", chatbot_id);
                HttpResponse::NotFound().json(json!({"status": "fail","message": message}))
            } else {
                HttpResponse::NoContent().finish()
            }
        }
        Err(e) => {
            let message = format!("Internal server error: {}", e);
            HttpResponse::InternalServerError().json(json!({"status": "error","message": message}))
        }
    }
}


pub fn config(conf: &mut web::ServiceConfig) {
    let scope = web::scope("/api")
        .service(health_checker_handler)
        .service(create_chatbot_handler)
        .service(get_chatbot_handler)
        .service(list_chatbot_handler)
        .service(delete_chatbot_handler);

    conf.service(scope);
}