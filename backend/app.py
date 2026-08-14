from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import joblib

from predict import clean_text
from auth import hash_password, verify_password
from database import get_connection
import sqlite3


# ==================================================
# FASTAPI APP
# ==================================================

app = FastAPI(
    title="AI SMS Spam Detection API",
    description="API for detecting Spam and Not Spam SMS",
    version="1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================================================
# LOAD ML MODEL
# ==================================================

model = joblib.load("spam_model.pkl")
vectorizer = joblib.load("vectorizer.pkl")


# ==================================================
# REQUEST MODELS
# ==================================================

class SMSRequest(BaseModel):
    message: str
    user_id: int


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


# ==================================================
# HOME API
# ==================================================

@app.get("/")
def home():
    return {
        "message": "AI SMS Spam Detection API is running"
    }


# ==================================================
# PREDICT API
# ==================================================

@app.post("/predict")
def predict_sms(request: SMSRequest):

    connection = get_connection()
    cursor = connection.cursor()

    try:

        # ------------------------------------------
        # Check whether user exists
        # ------------------------------------------

        cursor.execute(
            "SELECT id FROM users WHERE id = ?",
            (request.user_id,)
        )

        user = cursor.fetchone()

        if not user:
            return {
                "message": "User not found"
            }

        # ------------------------------------------
        # Original SMS
        # ------------------------------------------

        message = request.message

        # ------------------------------------------
        # Clean SMS
        # ------------------------------------------

        cleaned_message = clean_text(message)

        # ------------------------------------------
        # Convert SMS to TF-IDF
        # ------------------------------------------

        message_vector = vectorizer.transform(
            [cleaned_message]
        )

        # ------------------------------------------
        # ML Prediction
        # ------------------------------------------

        prediction = model.predict(
            message_vector
        )[0]

        # ------------------------------------------
        # Prediction Probability
        # ------------------------------------------

        probabilities = model.predict_proba(
            message_vector
        )[0]

        # ------------------------------------------
        # Confidence
        # ------------------------------------------

        confidence = max(probabilities) * 100

        # ------------------------------------------
        # Convert prediction to text
        # ------------------------------------------

        if prediction == 1:
            result = "Spam"
        else:
            result = "Not Spam"

        confidence = round(confidence, 2)

        # ------------------------------------------
        # Save prediction history
        # ------------------------------------------

        cursor.execute(
            """
            INSERT INTO prediction_history
            (
                user_id,
                message,
                prediction,
                confidence
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                request.user_id,
                message,
                result,
                confidence
            )
        )

        connection.commit()

        # ------------------------------------------
        # Return result
        # ------------------------------------------

        return {
            "message": message,
            "prediction": result,
            "confidence": confidence,
            "user_id": request.user_id
        }

    except Exception as e:

        connection.rollback()

        return {
            "message": "Prediction failed",
            "error": str(e)
        }

    finally:

        cursor.close()
        connection.close()


# ==================================================
# REGISTER API
# ==================================================

@app.post("/register")
def register_user(request: RegisterRequest):

    connection = get_connection()
    cursor = connection.cursor()

    try:

        # ------------------------------------------
        # Check existing email
        # ------------------------------------------

        cursor.execute(
            """
            SELECT id
            FROM users
            WHERE email = ?
            """,
            (request.email,)
        )

        existing_user = cursor.fetchone()

        if existing_user:
            return {
                "message": "Email already registered"
            }

        # ------------------------------------------
        # Hash password
        # ------------------------------------------

        hashed_password = hash_password(
            request.password
        )

        # ------------------------------------------
        # Insert user
        # ------------------------------------------

        cursor.execute(
            """
            INSERT INTO users
            (
                name,
                email,
                password
            )
            VALUES (?, ?, ?)
            """,
            (
                request.name,
                request.email,
                hashed_password
            )
        )

        user_id = cursor.lastrowid

        connection.commit()

        return {
            "message": "Registration successful",
            "user_id": user_id
        }

    except Exception as e:

        connection.rollback()

        return {
            "message": "Registration failed",
            "error": str(e)
        }

    finally:

        cursor.close()
        connection.close()


# ==================================================
# LOGIN API
# ==================================================

@app.post("/login")
def login_user(request: LoginRequest):

    connection = get_connection()
    cursor = connection.cursor()

    try:

        # ------------------------------------------
        # Find user
        # ------------------------------------------

        cursor.execute(
            """
            SELECT
                id,
                name,
                email,
                password
            FROM users
            WHERE email = ?
            """,
            (request.email,)
        )

        user = cursor.fetchone()

        # ------------------------------------------
        # Email not found
        # ------------------------------------------

        if not user:
            return {
                "message": "Invalid email or password"
            }

        # ------------------------------------------
        # Verify password
        # ------------------------------------------

        password_correct = verify_password(
            request.password,
            user["password"]
        )

        if not password_correct:
            return {
                "message": "Invalid email or password"
            }

        # ------------------------------------------
        # Login successful
        # ------------------------------------------

        return {
            "message": "Login successful",
            "user_id": user["id"],
            "name": user["name"],
            "email": user["email"]
        }

    except Exception as e:

        return {
            "message": "Login failed",
            "error": str(e)
        }

    finally:

        cursor.close()
        connection.close()


# ==================================================
# HISTORY API
# ==================================================

@app.get("/history/{user_id}")
def get_history(user_id: int):

    connection = get_connection()
    cursor = connection.cursor()

    try:

        # ------------------------------------------
        # Get user's prediction history
        # ------------------------------------------

        cursor.execute(
            """
            SELECT
                id,
                message,
                prediction,
                confidence,
                created_at
            FROM prediction_history
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (user_id,)
        )

        history = cursor.fetchall()

        # ------------------------------------------
        # Convert SQLite rows to JSON
        # ------------------------------------------

        result = []

        for row in history:

            result.append({
                "id": row["id"],
                "message": row["message"],
                "prediction": row["prediction"],
                "confidence": row["confidence"],
                "created_at": row["created_at"]
            })

        return {
            "user_id": user_id,
            "count": len(result),
            "history": result
        }

    except Exception as e:

        return {
            "message": "Failed to get history",
            "error": str(e)
        }

    finally:

        cursor.close()
        connection.close()

        # ==================================================
# DELETE SINGLE HISTORY
# ==================================================

@app.delete("/history/{history_id}/{user_id}")
def delete_history(history_id: int, user_id: int):

    connection = get_connection()
    cursor = connection.cursor()

    try:

        # Check that this history belongs to this user
        cursor.execute(
            """
            SELECT id
            FROM prediction_history
            WHERE id = ? AND user_id = ?
            """,
            (history_id, user_id)
        )

        history = cursor.fetchone()

        if not history:
            return {
                "success": False,
                "message": "History not found"
            }

        # Delete permanently
        cursor.execute(
            """
            DELETE FROM prediction_history
            WHERE id = ? AND user_id = ?
            """,
            (history_id, user_id)
        )

        connection.commit()

        return {
            "success": True,
            "message": "History deleted successfully",
            "history_id": history_id
        }

    except Exception as e:

        connection.rollback()

        return {
            "success": False,
            "message": "Failed to delete history",
            "error": str(e)
        }

    finally:

        cursor.close()
        connection.close()


 # =========================================================
# ADMIN STATISTICS
# =========================================================

@app.get("/admin/stats")
def admin_stats():
    try:
        conn = sqlite3.connect("sms_spam.db")
        cursor = conn.cursor()

        # Total registered users
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]

        # Total predictions
        cursor.execute("SELECT COUNT(*) FROM prediction_history")
        total_predictions = cursor.fetchone()[0]

        # Total spam messages
        cursor.execute("""
            SELECT COUNT(*)
            FROM prediction_history
            WHERE prediction = ?
        """, ("Spam",))

        spam_count = cursor.fetchone()[0]

        # Total safe messages
        cursor.execute("""
            SELECT COUNT(*)
            FROM prediction_history
            WHERE prediction = ?
        """, ("Ham",))

        safe_count = cursor.fetchone()[0]

        conn.close()

        return {
            "success": True,
            "total_users": total_users,
            "total_predictions": total_predictions,
            "spam_count": spam_count,
            "safe_count": safe_count
        }

    except Exception as e:

        return {
            "success": False,
            "message": "Failed to load admin statistics",
            "error": str(e)
        }


class AdminLoginRequest(BaseModel):
    username: str
    password: str


@app.post("/admin/login")
def admin_login(data: AdminLoginRequest):

    if (
        data.username == "admin"
        and data.password == "admin123"
    ):
        return {
            "success": True,
            "message": "Admin login successful",
            "username": "admin"
        }

    return {
        "success": False,
        "message": "Invalid admin username or password"
    }