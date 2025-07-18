from flask import Flask, render_template, Response, jsonify, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import cv2
import requests
import base64
from datetime import datetime
import os

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here' # Needed for flash messages

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///students.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Face++ API credentials
API_URL = "https://api-us.faceplusplus.com/facepp/v3/compare"
API_KEY = "fCpierN5zpjsgLBKK_u6PmFUQ8oJ_9Tz" # Replace with your actual API Key
API_SECRET = "sBW73pomaP9ysBaKCbu0YzG1MJBjG6aH" # Replace with your actual API Secret

# Ensure the uploads directory exists
UPLOAD_FOLDER = 'static/uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Database Models
class Student(db.Model):
    """
    Model ya hifadhidata kwa taarifa za mwanafunzi.
    """
    id = db.Column(db.Integer, primary_key=True)
    registration_number = db.Column(db.String(80), unique=True, nullable=False)
    firstname = db.Column(db.String(120), nullable=False)
    middlename = db.Column(db.String(120))
    department = db.Column(db.String(120))
    programme = db.Column(db.String(120))
    academic_year = db.Column(db.String(20))
    year_of_study = db.Column(db.String(20))
    semester = db.Column(db.String(20))
    registration_status = db.Column(db.Integer, default=0) # 1 for registered, 0 for not registered
    passport_size_path = db.Column(db.String(255)) # Path to the uploaded passport size image (relative to static)
    attendance_records = db.relationship('AttendanceRecord', backref='student', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Student {self.registration_number}>'

class AttendanceRecord(db.Model):
    """
    Model ya hifadhidata kwa rekodi za mahudhurio ya mwanafunzi.
    """
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    record_type = db.Column(db.String(10), nullable=False) # 'signin' or 'signout'

    def __repr__(self):
        return f'<AttendanceRecord {self.student_id} {self.record_type} at {self.timestamp}>'

# Initialize camera
camera = cv2.VideoCapture(0) # use 0 for default webcam

@app.route('/')
def index():
    """
    Njia kuu ya programu, inaonyesha ukurasa wa kuchanganua uso.
    """
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    """
    Hutoa mpasho wa video wa moja kwa moja kutoka kwa kamera.
    """
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

def gen_frames():
    """
    Hutoa fremu za video kutoka kwa kamera na kufanya uthibitishaji wa uso.
    """
    while True:
        success, frame = camera.read()
        if not success:
            break
        else:
            # Punguza ukubwa wa fremu ya kamera kwa utendaji bora
            frame = cv2.resize(frame, (640, 480))

            # Encode frame as JPG to compare via API
            ret, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()

            # Hifadhi fremu ya sasa kwa ajili ya kulinganisha
            cv2.imwrite('current_frame.jpg', frame)

            # Hapa tutafanya uthibitishaji wa uso na Face++ API
            # Kwa sasa, tutaonyesha tu fremu ya kamera
            # Mantiki ya kulinganisha itajumuishwa baadaye
            match_text = "Tafadhali Ingia/Toka"
            cv2.putText(frame, match_text, (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/scan', methods=['POST'])
def scan():
    """
    Hushughulikia ombi la kuchanganua uso na kulinganisha na hifadhidata.
    """
    record_type = request.form.get('record_type')
    if not record_type:
        return jsonify({"status": "error", "message": "Aina ya rekodi haijabainishwa (signin/signout)."})

    # Pata fremu ya sasa iliyohifadhiwa
    if not os.path.exists('current_frame.jpg'):
        return jsonify({"status": "error", "message": "Hakuna fremu ya kamera iliyopatikana."})

    with open('current_frame.jpg', 'rb') as f:
        live_img_data = f.read()

    # Pata wanafunzi wote kutoka hifadhidata
    students = Student.query.all()
    if not students:
        return jsonify({"status": "error", "message": "Hakuna wanafunzi waliosajiliwa kwenye hifadhidata."})

    best_match = None
    highest_confidence = 0

    for student in students:
        # Construct full path to passport image for comparison
        full_passport_path = os.path.join(app.root_path, 'static', student.passport_size_path)
        
        if student.passport_size_path and os.path.exists(full_passport_path):
            with open(full_passport_path, 'rb') as f:
                reference_img_data = f.read()

            files = {
                "image_file1": ("reference.jpg", reference_img_data),
                "image_file2": ("live.jpg", live_img_data)
            }
            data = {
                "api_key": API_KEY,
                "api_secret": API_SECRET
            }
            try:
                r = requests.post(API_URL, files=files, data=data, timeout=5)
                result = r.json()
                confidence = result.get("confidence", 0)

                if confidence > highest_confidence:
                    highest_confidence = confidence
                    best_match = student

            except Exception as e:
                print(f"API Error for student {student.registration_number}: {e}")
                continue # Endelea na mwanafunzi anayefuata

    if best_match and highest_confidence >= 70: # Tumia kizingiti cha 70% kwa ulinganifu
        # Rekodi mahudhurio
        new_record = AttendanceRecord(student_id=best_match.id, record_type=record_type)
        db.session.add(new_record)
        db.session.commit()

        # passport_size_path is already relative to static, so use it directly
        passport_url = url_for('static', filename=best_match.passport_size_path)

        student_info = {
            "registration_number": best_match.registration_number,
            "firstname": best_match.firstname,
            "middlename": best_match.middlename,
            "department": best_match.department,
            "programme": best_match.programme,
            "academic_year": best_match.academic_year,
            "year_of_study": best_match.year_of_study,
            "semester": best_match.semester,
            "registration_status": "Amesajiliwa" if best_match.registration_status == 1 else "Haijasajiliwa",
            "passport_size_url": passport_url,
            "confidence": f"{highest_confidence:.2f}%",
            "status": "SUCCESS"
        }
        return jsonify({"status": "success", "message": "Ulinganifu umefanikiwa!", "student_info": student_info})
    else:
        return jsonify({"status": "danger", "message": "Ulinganifu haukufanikiwa au hakuna mwanafunzi aliyepatikana."})

@app.route('/register_student', methods=['GET', 'POST'])
def register_student():
    """
    Njia ya kusajili mwanafunzi mpya.
    """
    if request.method == 'POST':
        reg_no = request.form['registration_number']
        fname = request.form['firstname']
        mname = request.form.get('middlename', '')
        dept = request.form.get('department', '')
        prog = request.form.get('programme', '')
        acad_year = request.form.get('academic_year', '')
        year_study = request.form.get('year_of_study', '')
        sem = request.form.get('semester', '')
        reg_status = 1 if 'registration_status' in request.form else 0
        passport_file = request.files['passport_size']

        if passport_file:
            filename = f"{reg_no}_{passport_file.filename}"
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            passport_file.save(filepath)
            # Store path relative to static folder in the database, ensure forward slashes for URL consistency
            passport_path_to_db = os.path.join('uploads', filename).replace('\\', '/')
        else:
            passport_path_to_db = None

        new_student = Student(
            registration_number=reg_no,
            firstname=fname,
            middlename=mname,
            department=dept,
            programme=prog,
            academic_year=acad_year,
            year_of_study=year_study,
            semester=sem,
            registration_status=reg_status,
            passport_size_path=passport_path_to_db
        )
        db.session.add(new_student)
        db.session.commit()
        flash('Mwanafunzi amesajiliwa kwa mafanikio!', 'success')
        return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/edit_student/<int:student_id>', methods=['GET', 'POST'])
def edit_student(student_id):
    """
    Njia ya kuhariri taarifa za mwanafunzi.
    """
    student = Student.query.get_or_404(student_id)
    if request.method == 'POST':
        student.registration_number = request.form['registration_number']
        student.firstname = request.form['firstname']
        student.middlename = request.form.get('middlename', '')
        student.department = request.form.get('department', '')
        student.programme = request.form.get('programme', '')
        student.academic_year = request.form.get('academic_year', '')
        student.year_of_study = request.form.get('year_of_study', '')
        student.semester = request.form.get('semester', '')
        student.registration_status = 1 if 'registration_status' in request.form else 0

        passport_file = request.files.get('passport_size')
        if passport_file and passport_file.filename != '':
            # Delete old passport image if it exists
            if student.passport_size_path:
                old_filepath = os.path.join(app.root_path, 'static', student.passport_size_path)
                if os.path.exists(old_filepath):
                    os.remove(old_filepath)

            filename = f"{student.registration_number}_{passport_file.filename}"
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            passport_file.save(filepath)
            student.passport_size_path = os.path.join('uploads', filename).replace('\\', '/') # Store relative path
        
        db.session.commit()
        flash('Taarifa za mwanafunzi zimehaririwa kwa mafanikio!', 'success')
        return redirect(url_for('view_students'))
    return render_template('edit_student.html', student=student)

@app.route('/delete_student/<int:student_id>', methods=['POST'])
def delete_student(student_id):
    """
    Njia ya kufuta mwanafunzi na rekodi zake zote.
    """
    student = Student.query.get_or_404(student_id)
    
    # Delete passport image file
    if student.passport_size_path:
        # Construct the full file path from the relative path stored in DB
        full_file_path = os.path.join(app.root_path, 'static', student.passport_size_path)
        if os.path.exists(full_file_path):
            os.remove(full_file_path)

    db.session.delete(student)
    db.session.commit()
    flash('Mwanafunzi amefutwa kwa mafanikio!', 'success')
    return redirect(url_for('view_students'))

@app.route('/view_students')
def view_students():
    """
    Njia ya kuonyesha orodha ya wanafunzi wote.
    """
    students = Student.query.all()
    return render_template('view_students.html', students=students)

@app.route('/view_attendance/<int:student_id>')
def view_attendance(student_id):
    """
    Njia ya kuonyesha rekodi za mahudhurio kwa mwanafunzi maalum.
    """
    student = Student.query.get_or_404(student_id)
    attendance_records = AttendanceRecord.query.filter_by(student_id=student_id).order_by(AttendanceRecord.timestamp.desc()).all()
    return render_template('view_attendance.html', student=student, records=attendance_records)


@app.route('/health')
def health():
    """
    Njia ya kuangalia afya ya programu.
    """
    return jsonify({"status": "running"})

if __name__ == '__main__':
    # Unda meza za hifadhidata kabla ya kuanza programu
    with app.app_context():
        db.create_all()
    app.run(debug=True)
