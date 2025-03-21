import os
from datetime import datetime, timedelta
from flask import Flask, send_file, redirect, url_for, request, jsonify
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from pymongo import MongoClient
from bson import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import random
import string
load_dotenv()

app = Flask(__name__, static_folder="src", static_url_path="")

# JWT Configuration
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "super-secret-key")
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=1)
jwt = JWTManager(app)

# MongoDB Connection
mongo_url = os.getenv("MONGO_URL")
try:
    client = MongoClient(mongo_url)
    print("MongoDB connected")
except Exception as e:
    print("Error connecting to MongoDB:", e)
db = client["edubridge_db"]
users_collection = db["users"]
announcements_collection = db["announcements"]
classrooms_collection = db["classrooms"]


"""
Intended Schemas:

Users Collection:
{
  "_id": ObjectId,
  "fullName": string,
  "email": string,
  "password": string (hashed),
  "phone": string,
  "institution": string,
  "department": string,   // For teachers
  "title": string,        // For teachers
  "bio": string,
  "userType": "teacher" or "student",
  "createdAt": datetime
}

Announcements Collection:
{
  "_id": ObjectId,
  "teacher_id": ObjectId,    // Reference to the teacher in users
  "text": string,
  "postTime": datetime,
  "comments": [
      {
         "commenter_id": ObjectId,
         "text": string,
         "commentTime": datetime
      },
      ...
  ]
}

Classrooms Collection:
{
  "_id": ObjectId,
  "teacher_id": ObjectId,
  "className": string,
  "subject": string,
  "section": string,
  "room": string,
  "createdAt": datetime,
  "enrolled_students": [ObjectId, ...]
}
"""

# -------------------------
# Routes for Static Pages
# -------------------------
@app.route("/")
def index():
    return send_file('src/index.html')

@app.route("/login")
def login():
    return send_file('src/login.html')

@app.route("/signup")
def signup():
    return send_file('src/signup.html')

@app.route("/get-started")
def get_started():
    return redirect(url_for('signup'))

@app.route("/teacher_dashboard")
def teacher_dashboard():
    return send_file('src/teacher_after_login.html')

@app.route("/teacher_classroom")
def teacher_classroom():
    return send_file('src/teacher_classroom.html')

@app.route("/teacher_profile")
def teacher_profile():
    return send_file('src/teacher_profile_page.html')

@app.route("/dashboard")
def dashboard():
    return send_file('src/dashboard.html')

@app.route("/profile")
def profile():
    return send_file('src/profile.html')

@app.route("/announcements")
def announcements():
    return send_file('src/announcements.html')

@app.route("/courses")
def courses():
    return send_file('src/courses.html')

@app.route("/calendar")
def calendar():
    return send_file('src/calendar.html')

@app.route("/settings")
def settings():
    return send_file('src/settings.html')

# -------------------------
# API Endpoints
# -------------------------

# Signup API – expects JSON with fullName, email, password, (optional phone, institution, department, title, bio) and userType.
@app.route("/api/signup", methods=["POST"])
def api_signup():
    data = request.get_json()
    if not data:
        return jsonify({"msg": "No input data provided"}), 400

    email = data.get("email")
    if users_collection.find_one({"email": email}):
        return jsonify({"msg": "User already exists"}), 400

    hashed_pw = generate_password_hash(data.get("password"))
    user = {
        "fullName": data.get("fullName"),
        "email": email,
        "password": hashed_pw,
        "phone": data.get("phone", ""),
        "institution": data.get("institution", ""),
        "department": data.get("department", ""),
        "title": data.get("title", ""),
        "bio": data.get("bio", ""),
        "userType": data.get("userType"),  # "teacher" or "student"
        "createdAt": datetime.utcnow()
    }
    result = users_collection.insert_one(user)
    return jsonify({"msg": "Signup successful", "user_id": str(result.inserted_id)}), 201

# Login API – verifies email and password, returns a JWT token on success.
@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json()
    if not data:
        return jsonify({"msg": "No input data provided"}), 400

    email = data.get("email")
    password = data.get("password")
    user = users_collection.find_one({"email": email})
    if not user or not check_password_hash(user["password"], password):
        return jsonify({"msg": "Invalid email or password"}), 401

    access_token = create_access_token(identity=str(user["_id"]))
    return jsonify({"msg": "Login successful", "access_token": access_token, "userType": user["userType"]}), 200

# Get Profile API – returns user profile (except password) for the authenticated user.
@app.route("/api/profile", methods=["GET"])
@jwt_required()
def get_profile():
    user_id = get_jwt_identity()
    user = users_collection.find_one({"_id": ObjectId(user_id)})
    if not user:
        return jsonify({"msg": "User not found"}), 404
    user["_id"] = str(user["_id"])
    user.pop("password", None)
    return jsonify(user), 200

# Update Profile API – accepts JSON with updated profile fields.
@app.route("/api/profile", methods=["PUT"])
@jwt_required()
def update_profile():
    user_id = get_jwt_identity()
    data = request.get_json()
    update_data = {
        "fullName": data.get("fullName"),
        "email": data.get("email"),
        "phone": data.get("phone", ""),
        "institution": data.get("institution", ""),
        "department": data.get("department", ""),
        "title": data.get("title", ""),
        "bio": data.get("bio", "")
    }
    users_collection.update_one({"_id": ObjectId(user_id)}, {"$set": update_data})
    return jsonify({"msg": "Profile updated"}), 200

# Announcements API – POST to create an announcement.
@app.route("/api/announcements", methods=["POST"])
@jwt_required()
def post_announcement():
    user_id = get_jwt_identity()
    data = request.get_json()
    text = data.get("text")
    if not text:
        return jsonify({"msg": "Announcement text is required"}), 400

    announcement = {
        "teacher_id": ObjectId(user_id),
        "text": text,
        "postTime": datetime.utcnow(),
        "comments": []
    }
    result = announcements_collection.insert_one(announcement)
    announcement["_id"] = str(result.inserted_id)
    announcement["teacher_id"] = user_id
    announcement["postTime"] = announcement["postTime"].isoformat()
    return jsonify({"msg": "Announcement posted", "announcement": announcement}), 201

# GET all announcements.
@app.route("/api/announcements", methods=["GET"])
@jwt_required()
def get_announcements():
    announcements = []
    for a in announcements_collection.find().sort("postTime", -1):
        a["_id"] = str(a["_id"])
        a["teacher_id"] = str(a["teacher_id"])
        a["postTime"] = a["postTime"].isoformat()
        for comment in a.get("comments", []):
            comment["commentTime"] = comment["commentTime"].isoformat()
            comment["commenter_id"] = str(comment["commenter_id"])
        announcements.append(a)
    return jsonify(announcements), 200

# Edit an announcement.
@app.route("/api/announcements/<announcement_id>", methods=["PUT"])
@jwt_required()
def edit_announcement(announcement_id):
    data = request.get_json()
    new_text = data.get("text")
    if not new_text:
        return jsonify({"msg": "New text is required"}), 400
    announcements_collection.update_one({"_id": ObjectId(announcement_id)}, {"$set": {"text": new_text}})
    return jsonify({"msg": "Announcement updated"}), 200

# Delete an announcement.
@app.route("/api/announcements/<announcement_id>", methods=["DELETE"])
@jwt_required()
def delete_announcement(announcement_id):
    announcements_collection.delete_one({"_id": ObjectId(announcement_id)})
    return jsonify({"msg": "Announcement deleted"}), 200

# Add a comment to an announcement.
@app.route("/api/announcements/<announcement_id>/comments", methods=["POST"])
@jwt_required()
def post_comment(announcement_id):
    user_id = get_jwt_identity()
    data = request.get_json()
    text = data.get("text")
    if not text:
        return jsonify({"msg": "Comment text is required"}), 400
    comment = {
        "commenter_id": ObjectId(user_id),
        "text": text,
        "commentTime": datetime.utcnow()
    }
    announcements_collection.update_one({"_id": ObjectId(announcement_id)}, {"$push": {"comments": comment}})
    comment["commentTime"] = comment["commentTime"].isoformat()
    comment["commenter_id"] = user_id
    return jsonify({"msg": "Comment added", "comment": comment}), 201

# Classrooms API – create a classroom.
# Predefined list of background images
BACKGROUND_IMAGES = [
    'https://www.gstatic.com/classroom/themes/img_graduation.jpg',
    'https://www.gstatic.com/classroom/themes/img_code.jpg',
    'https://www.gstatic.com/classroom/themes/img_bookclub.jpg',
    'https://www.gstatic.com/classroom/themes/img_breakfast.jpg',
    'https://www.gstatic.com/classroom/themes/img_reachout.jpg',
    'https://www.gstatic.com/classroom/themes/img_learnlanguage.jpg'
]

# Helper function to generate a random classroom code
def generate_class_code(length=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))


@app.route("/api/classrooms", methods=["POST"])
@jwt_required()
def create_classroom():
    user_id = get_jwt_identity()
    data = request.get_json()
    
    # Generate a unique classroom code
    class_code = generate_class_code()
    while classrooms_collection.find_one({"classCode": class_code}):
        class_code = generate_class_code()
    
    # Randomly choose a background image from the list
    header_image = random.choice(BACKGROUND_IMAGES)

    classroom = {
        "teacher_id": ObjectId(user_id),
        "className": data.get("className"),
        "subject": data.get("subject"),
        "section": data.get("section"),
        "room": data.get("room"),
        "classCode": class_code,
        "headerImage": header_image,  # Save the chosen image
        "createdAt": datetime.utcnow(),
        "enrolled_students": []
    }
    result = classrooms_collection.insert_one(classroom)
    classroom["_id"] = str(result.inserted_id)
    classroom["teacher_id"] = user_id
    classroom["createdAt"] = classroom["createdAt"].isoformat()
    return jsonify({"msg": "Classroom created", "classroom": classroom}), 201


# Get classrooms – for teachers, return those they created; for students, those they’re enrolled in.
@app.route("/api/classrooms", methods=["GET"])
@jwt_required()
def get_classrooms():
    user_id = get_jwt_identity()
    user = users_collection.find_one({"_id": ObjectId(user_id)})
    classrooms = []
    if user["userType"] == "teacher":
        query = {"teacher_id": ObjectId(user_id)}
    else:
        query = {"enrolled_students": ObjectId(user_id)}
    for c in classrooms_collection.find(query).sort("createdAt", -1):
        # Get the teacher's details before converting teacher_id to string.
        teacher = users_collection.find_one({"_id": c["teacher_id"]})
        c["teacherName"] = teacher["fullName"] if teacher else ""
        c["_id"] = str(c["_id"])
        c["teacher_id"] = str(c["teacher_id"])
        c["createdAt"] = c["createdAt"].isoformat()
        c["enrolled_students"] = [str(s) for s in c.get("enrolled_students", [])]
        c["headerImage"] = c.get("headerImage", random.choice(BACKGROUND_IMAGES))
        classrooms.append(c)
    return jsonify(classrooms), 200

@app.route("/api/classrooms/join", methods=["POST"])
@jwt_required()
def join_classroom():
    user_id = get_jwt_identity()
    data = request.get_json()
    class_code = data.get("classCode")
    
    if not class_code:
        return jsonify({"msg": "Class code is required"}), 400

    classroom = classrooms_collection.find_one({"classCode": class_code})
    if not classroom:
        return jsonify({"msg": "Invalid class code"}), 404

    # Check if student is already enrolled
    if ObjectId(user_id) in classroom.get("enrolled_students", []):
        return jsonify({"msg": "You are already enrolled in this class"}), 400

    classrooms_collection.update_one(
        {"_id": classroom["_id"]},
        {"$push": {"enrolled_students": ObjectId(user_id)}}
    )
    return jsonify({"msg": "Successfully joined the class", "classroomId": str(classroom["_id"])}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, port=port)
