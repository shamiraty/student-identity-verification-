import requests
import json
from PIL import Image
from IPython.display import display
from io import BytesIO

# ---------- CONFIGURATION ----------
api_key = "fCpierN5zpjsgLBKK_u6PmFUQ8oJ_9Tz"
api_secret = "sBW73pomaP9ysBaKCbu0YzG1MJBjG6aH"

img1_path = "2018.jpg"
img2_path = "2014 B.jpg"

# ---------- SHOW IMAGES (RESIZED) ----------
print("📸 First Image:")
img1 = Image.open(img1_path).resize((200, 200))
display(img1)

print("📸 Second Image:")
img2 = Image.open(img2_path).resize((200, 200))
display(img2)

# ---------- SEND API REQUEST ----------
url = "https://api-us.faceplusplus.com/facepp/v3/compare"
files = {
    "image_file1": open(img1_path, "rb"),
    "image_file2": open(img2_path, "rb")
}
data = {
    "api_key": api_key,
    "api_secret": api_secret
}

response = requests.post(url, files=files, data=data)
result = response.json()

# ---------- SAVE RESPONSE TO FILE ----------
with open("face_compare_result.json", "w") as f:
    json.dump(result, f, indent=4)

# ---------- DISPLAY RESULT ----------
print("\n✅ API Response:")
if 'confidence' in result:
    confidence = result["confidence"]
    print(f"\n🔍 Similarity Confidence: {confidence}")

    # Simple decision logic without printing thresholds
    if confidence >= result.get("thresholds", {}).get("1e-5", 90):
        print("🟢 Most likely the same person.")
    elif confidence >= result.get("thresholds", {}).get("1e-3", 65):
        print("🟡 Possibly the same person, but not certain.")
    else:
        print("🔴 Likely not the same person.")

    # Show face tokens if available
    if result.get("faces1") and result.get("faces2"):
        face1 = result["faces1"][0]
        face2 = result["faces2"][0]
        print("\n🧍 First face token:", face1["face_token"])
        print("🧍 Second face token:", face2["face_token"])
else:
    print("❌ Error or face not detected:")
    print(result.get("error_message", "Unknown issue."))
