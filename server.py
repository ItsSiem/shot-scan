from flask import Flask, request, jsonify, send_file, render_template
from flask_cors import CORS
import cv2
import numpy as np
import os

app = Flask(__name__)
CORS(app)
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def calculate_score(reference_circle, bullet_circle):
    reference_radius_mm = 15.25  # Reference radius in mm
    # Ensure the reference circle radius is not too large or too small
    if reference_circle[2] <= 0:
        return 0  # Return 0 if radius is invalid

    derived_milli = reference_circle[2] / reference_radius_mm

    # Ensure that the calculated distance is not too large or negative
    dist = np.sqrt((bullet_circle[0] - reference_circle[0]) * (bullet_circle[0] - reference_circle[0]) + (bullet_circle[1] - reference_circle[1]) * (bullet_circle[1] - reference_circle[1]))
    
    # Apply a threshold for distance to prevent overflow
    max_dist = 1000  # You can adjust this threshold based on expected distances
    if dist > max_dist:
        dist = max_dist  # Cap the distance to avoid overflow

    score = max(0, 10.9 - (dist / (2.5 * derived_milli)))  # Map distance to score
    return round(score, 1)

def process_image(image_path, dp, minDist, param1, param2, minRadius, maxRadius):
    image = cv2.imread(image_path, cv2.IMREAD_COLOR)
    original_height, original_width = image.shape[:2]
    scale_factor = 1024 / float(original_width)
    target_height = int(original_height * scale_factor)
    resized_image = cv2.resize(image, (1024, target_height))

    gray = cv2.cvtColor(resized_image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.medianBlur(gray, 25)
    
    # Detect circles with dynamic parameters
    circles = cv2.HoughCircles(
        blurred, 
        cv2.HOUGH_GRADIENT, 
        dp=dp, 
        minDist=minDist, 
        param1=param1, 
        param2=param2, 
        minRadius=minRadius, 
        maxRadius=maxRadius
    )
    
    if circles is not None:
        circles = np.uint16(np.around(circles))
        reference_circle = circles[0][0]
        bullet_circle = None
        for i in circles[0, 1:]:
            if i[2] < reference_circle[2] / 2:
                bullet_circle = i
                break
        
        if bullet_circle is not None:
            score = calculate_score(reference_circle, bullet_circle)
            cv2.circle(resized_image, (bullet_circle[0], bullet_circle[1]), bullet_circle[2], (255, 0, 0), 2)
        else:
            score = None
        
        cv2.circle(resized_image, (reference_circle[0], reference_circle[1]), reference_circle[2], (0, 255, 0), 2)
    else:
        score = None
    
    output_path = os.path.join(UPLOAD_FOLDER, "output.png")
    cv2.imwrite(output_path, resized_image)
    return output_path, score


@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"})
    file = request.files["file"]
    
    # Get the parameters from the frontend
    dp = float(request.form.get("dp", 1.2))
    min_dist = int(request.form.get("minDist", 30))
    param1 = int(request.form.get("param1", 50))
    param2 = int(request.form.get("param2", 20))
    min_radius = int(request.form.get("minRadius", 5))
    max_radius = int(request.form.get("maxRadius", 100))
    
    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(file_path)
    
    processed_path, score = process_image(file_path, dp, min_dist, param1, param2, min_radius, max_radius)
    response = {"processed_image": processed_path, "score": score}
    return jsonify(response)

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_file(os.path.join(UPLOAD_FOLDER, filename))

@app.route("/")
def index():
    return render_template("index.html")  # Serve the HTML page

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
