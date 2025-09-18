import os
import json
import uuid
import google.generativeai as genai
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
from datetime import datetime

# --- SETUP ---

app = Flask(__name__)
load_dotenv()
CORS(app)

# Configure the Gemini API
try:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found. Please create a .env file with your key.")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    print(f"Error configuring Gemini API: {e}")
    model = None

# --- HELPER FUNCTIONS ---

def load_all_patient_data():
    """Loads the list of all patients from the JSON file."""
    with open('mock_data.json', 'r') as f:
        return json.load(f)

def save_all_patient_data(data):
    """Saves the entire list of patients back to the JSON file."""
    with open('mock_data.json', 'w') as f:
        json.dump(data, f, indent=2)

def load_users_data():
    """Loads the user data from the JSON file."""
    with open('users.json', 'r') as f:
        return json.load(f)

# --- API ENDPOINTS ---

@app.route("/")
def hello_world():
    return "The Synapse EMR backend is running!"

@app.route("/api/login", methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    try:
        users = load_users_data()
        user = users.get(username)
        if user and user.get('password') == password:
            return jsonify({"success": True, "message": "Login successful"})
        else:
            return jsonify({"error": "Invalid credentials"}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/patients")
def get_patients_list():
    """Returns a simplified list of all patients for the main directory."""
    try:
        patients = load_all_patient_data()
        patient_list = [{"id": p["id"], "name": p["name"], "dob": p["dob"], "profile_picture_url": p.get("profile_picture_url")} for p in patients]
        return jsonify(patient_list)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/patient/<patient_id>")
def get_patient_details(patient_id):
    """Returns all data for a specific patient."""
    try:
        patients = load_all_patient_data()
        patient = next((p for p in patients if p['id'] == patient_id), None)
        if patient:
            return jsonify(patient)
        else:
            return jsonify({"error": "Patient not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/patient/add", methods=['POST'])
def add_new_patient():
    """Adds a new patient to the database."""
    try:
        new_patient_data = request.get_json()
        all_patients = load_all_patient_data()
        
        # Basic validation
        if not new_patient_data.get('name') or not new_patient_data.get('dob'):
            return jsonify({"error": "Name and DOB are required."}), 400

        # Create a full patient object
        new_patient = {
            "id": "p" + str(uuid.uuid4())[:4],
            "name": new_patient_data.get('name'),
            "dob": new_patient_data.get('dob'),
            "gender": new_patient_data.get('gender'),
            "contact": new_patient_data.get('contact'),
            "profile_picture_url": new_patient_data.get('profile_picture_url') or f"https://placehold.co/100x100/c4b5fd/FFFFFF?text={new_patient_data.get('name', 'P')[0]}",
            "familyBackground": {},
            "healthRecords": [],
            "dentalRecords": [],
            "visionRecords": [],
            "medicalReports": []
        }
        
        all_patients.append(new_patient)
        save_all_patient_data(all_patients)
        
        return jsonify({"success": True, "message": "Patient added successfully", "patient": new_patient})

    except Exception as e:
        print(f"Error adding new patient: {e}")
        return jsonify({"error": "An internal server error occurred"}), 500


@app.route("/api/patient/<patient_id>/update", methods=['POST'])
def update_patient_record(patient_id):
    """Receives a full patient object and updates the database."""
    try:
        updated_patient_data = request.get_json()
        all_patients = load_all_patient_data()
        
        patient_found = False
        for i, p in enumerate(all_patients):
            if p['id'] == patient_id:
                all_patients[i] = updated_patient_data 
                patient_found = True
                break
        
        if patient_found:
            save_all_patient_data(all_patients)
            return jsonify({"success": True, "message": "Patient record updated successfully"})
        else:
            return jsonify({"error": "Patient not found"}), 404

    except Exception as e:
        print(f"Error updating patient record: {e}")
        return jsonify({"error": "An internal server error occurred"}), 500

@app.route("/api/patient/<patient_id>/add_medical_report", methods=['POST'])
def add_medical_report(patient_id):
    try:
        report_data = request.get_json()
        all_patients = load_all_patient_data()
        patient = next((p for p in all_patients if p['id'] == patient_id), None)

        if not patient:
            return jsonify({"error": "Patient not found"}), 404

        report_data['reportId'] = str(uuid.uuid4())
        if 'medicalReports' not in patient:
            patient['medicalReports'] = []
        patient['medicalReports'].append(report_data)

        # Sync General Health Data
        vitals = report_data.get('physicalExamination', {}).get('vitalSigns', {})
        if any(vitals.values()):
            health_record = {
                "date": report_data.get('dateOfVisit'),
                "systolic_bp": int(vitals.get('bp_systolic')) if vitals.get('bp_systolic') else None,
                "diastolic_bp": int(vitals.get('bp_diastolic')) if vitals.get('bp_diastolic') else None,
                "pulse": int(vitals.get('pulse')) if vitals.get('pulse') else None,
                "temperature": float(vitals.get('temperature')) if vitals.get('temperature') else None,
                "doctor_notes": f"Chief Complaint: {report_data.get('chiefComplaint', 'N/A')}. Assessment: {report_data.get('assessment', 'N/A')}"
            }
            if 'healthRecords' not in patient: patient['healthRecords'] = []
            patient['healthRecords'].append(health_record)

        # Sync Dental Data
        dental_exam = report_data.get('dentalExamination')
        if dental_exam:
            dental_record = {"date": report_data.get('dateOfVisit'), "procedure": "Clinical Examination", "dentist_notes": dental_exam}
            if 'dentalRecords' not in patient: patient['dentalRecords'] = []
            patient['dentalRecords'].append(dental_record)

        # Sync Vision Data
        vision_exam = report_data.get('visionExamination', {})
        if any(vision_exam.values()):
            vision_record = {
                "date": report_data.get('dateOfVisit'),
                "right_eye_sph": vision_exam.get('visualAcuity_rightEye', 'N/A'),
                "left_eye_sph": vision_exam.get('visualAcuity_leftEye', 'N/A'),
                "optometrist_notes": f"Fundus Exam: {vision_exam.get('fundusExam', 'N/A')}. Other Findings: {vision_exam.get('otherFindings', 'N/A')}"
            }
            if 'visionRecords' not in patient: patient['visionRecords'] = []
            patient['visionRecords'].append(vision_record)
            
        # Update patient in list and save
        for i, p in enumerate(all_patients):
            if p['id'] == patient_id:
                all_patients[i] = patient
                break
        
        save_all_patient_data(all_patients)
        
        return jsonify({"success": True, "message": "Medical report added and all sections synced."})

    except Exception as e:
        print(f"Error adding medical report: {e}")
        return jsonify({"error": "An internal server error occurred"}), 500

# --- AI ENDPOINTS ---

@app.route("/api/patient/<patient_id>/summary", methods=['POST'])
def get_ai_summary(patient_id):
    if not model:
        return jsonify({"error": "Gemini API not configured"}), 500

    try:
        data = request.get_json()
        section = data.get('section', 'general') # e.g., 'health', 'dental', 'vision'
        
        all_patients = load_all_patient_data()
        patient = next((p for p in all_patients if p['id'] == patient_id), None)
        if not patient:
            return jsonify({"error": "Patient not found"}), 404

        notes_to_summarize = ""
        # Prioritize the most recent full medical report for context
        if patient.get('medicalReports'):
            latest_report = patient['medicalReports'][-1]
            if section == 'health':
                notes_to_summarize = json.dumps(latest_report.get('physicalExamination'), indent=2) + "\n" + latest_report.get('assessment', '')
            elif section == 'dental':
                notes_to_summarize = latest_report.get('dentalExamination', '')
            elif section == 'vision':
                notes_to_summarize = json.dumps(latest_report.get('visionExamination'), indent=2)
        # Fallback to structured records if no report exists
        else:
            record_map = {'health': 'healthRecords', 'dental': 'dentalRecords', 'vision': 'visionRecords'}
            notes_to_summarize = json.dumps(patient.get(record_map.get(section, [])), indent=2)

        if not notes_to_summarize or notes_to_summarize.strip() in ["", "{}", "null"]:
            return jsonify({"summary": f"No recent {section} records available to summarize."})

        prompt = f"""
        Act as a medical AI assistant. Summarize the following clinical notes for the '{section}' section into 2-3 concise bullet points for a doctor.
        Focus on the most critical findings, diagnoses, or trends.

        Clinical Notes:
        {notes_to_summarize}
        """
        response = model.generate_content(prompt)
        return jsonify({"summary": response.text.strip()})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/patient/<patient_id>/ai_care_plan")
def get_ai_care_plan(patient_id):
    if not model:
        return jsonify({"error": "Gemini API not configured"}), 500
        
    try:
        all_patients = load_all_patient_data()
        patient = next((p for p in all_patients if p['id'] == patient_id), None)

        if not patient:
            return jsonify({"error": "Patient not found"}), 404

        prompt = f"""
        You are an expert clinical AI assistant. Generate a comprehensive care plan based on the patient's complete medical record.
        Analyze all provided information, especially the most recent medical reports.

        PATIENT'S FULL RECORD:
        ---
        Patient Info: {json.dumps({'name': patient.get('name'), 'dob': patient.get('dob'), 'gender': patient.get('gender')})}
        Family & Background: {json.dumps(patient.get('familyBackground'), indent=2)}
        ---
        Structured Health Records (Vitals): {json.dumps(patient.get('healthRecords'), indent=2)}
        ---
        Structured Dental Records: {json.dumps(patient.get('dentalRecords'), indent=2)}
        ---
        Structured Vision Records: {json.dumps(patient.get('visionRecords'), indent=2)}
        ---
        FULL MEDICAL REPORTS (Most Important): {json.dumps(patient.get('medicalReports'), indent=2)}
        ---

        Based on a holistic analysis, generate a structured care plan in Markdown format.
        Your response MUST be in the following format:

        ### Key Health Risks
        - **Risk 1:** (e.g., Elevated risk of cardiovascular disease due to family history and recent high blood pressure readings).
        - **Risk 2:** (e.g., Potential for progressive myopia based on vision records).

        ### Recommended Actions & Monitoring
        - **Action 1:** (e.g., Lifestyle: Recommend a low-sodium diet and 30 minutes of moderate exercise, 3-4 times a week).
        - **Action 2:** (e.g., Monitoring: Suggest weekly at-home blood pressure monitoring).

        ### Specialist Referrals
        - **Referral 1:** (e.g., Consider referral to a cardiologist for a full cardiovascular workup).

        Do NOT prescribe specific medications or dosages. The output must be professional, clear, and actionable for a clinician.
        """
        
        response = model.generate_content(prompt)
        return jsonify({"care_plan": response.text.strip()})
        
    except Exception as e:
        print(f"Error generating AI care plan: {e}")
        return jsonify({"error": f"An internal server error occurred: {e}"}), 500

@app.route("/api/patient/<patient_id>/ai_prescription")
def get_ai_prescription(patient_id):
    if not model:
        return jsonify({"error": "Gemini API not configured"}), 500
        
    try:
        all_patients = load_all_patient_data()
        patient = next((p for p in all_patients if p['id'] == patient_id), None)

        if not patient:
            return jsonify({"error": "Patient not found"}), 404

        prompt = f"""
        You are an AI clinical pharmacology assistant. Your task is to suggest a potential prescription based on a patient's complete medical record.
        This is a proof-of-concept tool and NOT for real-world clinical use.
        Analyze all the information provided, focusing on the chief complaint and assessment from the most recent medical report.

        PATIENT'S FULL RECORD:
        ---
        Patient Info: {json.dumps({'name': patient.get('name'), 'dob': patient.get('dob'), 'gender': patient.get('gender')})}
        Allergies: {json.dumps(patient.get('medicalReports', [{}])[-1].get('allergies'))}
        Current Medications: {json.dumps(patient.get('medicalReports', [{}])[-1].get('medications'))}
        ---
        FULL MEDICAL REPORTS (Analyze the most recent one for the primary diagnosis): {json.dumps(patient.get('medicalReports'), indent=2)}
        ---
        
        Based on the latest assessment and diagnosis, generate a sample prescription.
        Your response MUST be in the following Markdown format:

        ### Medication
        - **Drug Name:** (e.g., Lisinopril)
        - **Dosage:** (e.g., 10 mg)
        - **Frequency:** (e.g., Once daily)
        - **Route:** (e.g., Oral)

        ### Rationale
        - **Reasoning:** (e.g., "Prescribed for hypertension based on recent high blood pressure readings and the patient's assessment. Lisinopril is a common first-line treatment.")
        
        ### Important Considerations
        - **Monitoring:** (e.g., "Monitor blood pressure regularly. Check kidney function and potassium levels within 2-4 weeks of starting.")
        - **Side Effects:** (e.g., "Common side effects include a dry cough, dizziness, and headache.")

        Your output must be structured, professional, and include a clear rationale.
        """
        
        response = model.generate_content(prompt)
        return jsonify({"prescription": response.text.strip()})
        
    except Exception as e:
        print(f"Error generating AI prescription: {e}")
        return jsonify({"error": f"An internal server error occurred: {e}"}), 500


# --- RUN THE APP ---
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)

