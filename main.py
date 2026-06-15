"""
Smart Attendance Monitoring System with Facial Recognition
Enhanced Features: Attendance Percentage, Detained Students List, Academic Year Configuration
Fixed constructor and initialization issues
"""

import tkinter as tk
from tkinter import ttk, messagebox as mess, simpledialog as tsd
import cv2
import os
import csv
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import pandas as pd
import datetime
import time
import hashlib
import secrets
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Constants
MIN_CONFIDENCE = 50
MAX_SAMPLE_IMAGES = 100
HAAR_CASCADE_FILE = os.path.join(os.path.dirname(__file__), "haarcascade_frontalface_default.xml")
MINIMUM_ATTENDANCE_PERCENTAGE = 75  # Minimum required attendance percentage
DETAINED_THRESHOLD = 60  # Below this percentage, student is detained

# Reward thresholds (updated with percentage-based rewards)
REWARDS = {
    10: "10 Credits",
    30: "Badge of Honor", 
    50: "Attendance Certificate",
    75: "Excellence Award (75% Attendance)",
    90: "Perfect Attendance Award (90%+)"
}

class AttendanceSystem:
    def __init__(self):
        self.setup_directories()
        self.global_vars = {'key': ''}
        self.init_gui()
        
    def setup_directories(self):
        """Create necessary directories if they don't exist"""
        directories = [
            "StudentDetails",
            "TrainingImage", 
            "TrainingImageLabel",
            "Attendance",
            "Certificates",
            "AcademicConfig"
        ]
        for directory in directories:
            os.makedirs(directory, exist_ok=True)

    def hash_password(self, password):
        """Hash password securely"""
        salt = secrets.token_hex(16)
        pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return salt + pwd_hash.hex()

    def verify_password(self, password, stored_hash):
        """Verify password against hash"""
        if len(stored_hash) < 32:
            return False
        salt = stored_hash[:32]
        stored_pwd_hash = stored_hash[32:]
        pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return pwd_hash.hex() == stored_pwd_hash

    def validate_inputs(self, student_id, name, total_days=None):
        """Validate student inputs"""
        if not student_id or not student_id.strip():
            return False, "ID cannot be empty"
        if not student_id.isdigit():
            return False, "ID must be numeric"
        if not name or not name.strip():
            return False, "Name cannot be empty"
        if not name.replace(' ', '').replace('-', '').isalpha():
            return False, "Name must contain only letters, spaces, and hyphens"
        if len(name.strip()) < 2:
            return False, "Name must be at least 2 characters"
        if total_days is not None:
            if not total_days.isdigit() or int(total_days) < 1 or int(total_days) > 365:
                return False, "Total academic days must be between 1 and 365"
        return True, ""

    def check_haarcascade_file(self):
        """Check if Haar Cascade file exists"""
        if not os.path.isfile(HAAR_CASCADE_FILE):
            mess.showerror("File Missing", f"Please ensure {HAAR_CASCADE_FILE} exists in the current directory")
            self.window.destroy()
            return False
        return True

    def tick(self):
        """Update clock display"""
        time_string = time.strftime('%H:%M:%S')
        self.clock.config(text=time_string)
        self.clock.after(200, self.tick)

    def contact(self):
        """Show contact information"""
        mess.showinfo('Contact Us', "For support, please contact: support@attendancesystem.com")

    def save_password(self):
        """Save new password securely"""
        password_file = os.path.join("TrainingImageLabel", "psd.txt")
        
        if os.path.exists(password_file):
            with open(password_file, "r") as f:
                stored_hash = f.read().strip()
        else:
            self.master.destroy()
            new_pass = tsd.askstring('Setup Password', 'Enter a new password:', show='*')
            if not new_pass:
                mess.showerror('No Password', 'Password not set! Please try again')
                return
            
            hashed = self.hash_password(new_pass)
            with open(password_file, "w") as f:
                f.write(hashed)
            mess.showinfo('Password Set', 'New password registered successfully!')
            return

        old_pass = self.old.get()
        new_pass = self.new.get()
        confirm_pass = self.nnew.get()

        if not self.verify_password(old_pass, stored_hash):
            mess.showerror('Wrong Password', 'Incorrect old password')
            return

        if new_pass != confirm_pass:
            mess.showerror('Password Mismatch', 'New passwords do not match')
            return

        if len(new_pass) < 6:
            mess.showerror('Weak Password', 'Password must be at least 6 characters')
            return

        hashed = self.hash_password(new_pass)
        with open(password_file, "w") as f:
            f.write(hashed)
        
        mess.showinfo('Success', 'Password changed successfully!')
        self.master.destroy()

    def change_password(self):
        """Open password change dialog"""
        self.master = tk.Tk()
        self.master.geometry("450x180")
        self.master.resizable(False, False)
        self.master.title("Change Password")
        self.master.configure(background="white")

        tk.Label(self.master, text='Enter Old Password:', bg='white', 
                font=('Arial', 12, 'bold')).place(x=20, y=20)
        self.old = tk.Entry(self.master, width=25, font=('Arial', 12), show='*')
        self.old.place(x=200, y=20)

        tk.Label(self.master, text='Enter New Password:', bg='white', 
                font=('Arial', 12, 'bold')).place(x=20, y=60)
        self.new = tk.Entry(self.master, width=25, font=('Arial', 12), show='*')
        self.new.place(x=200, y=60)

        tk.Label(self.master, text='Confirm New Password:', bg='white', 
                font=('Arial', 12, 'bold')).place(x=20, y=100)
        self.nnew = tk.Entry(self.master, width=25, font=('Arial', 12), show='*')
        self.nnew.place(x=200, y=100)

        tk.Button(self.master, text="Cancel", command=self.master.destroy, 
                 fg="white", bg="red", width=15, font=('Arial', 10, 'bold')).place(x=240, y=140)
        tk.Button(self.master, text="Save", command=self.save_password, 
                 fg="white", bg="green", width=15, font=('Arial', 10, 'bold')).place(x=80, y=140)

    def authenticate_user(self):
        """Authenticate user before training"""
        password_file = os.path.join("TrainingImageLabel", "psd.txt")
        
        if not os.path.exists(password_file):
            new_pass = tsd.askstring('Setup Password', 'Enter a new password:', show='*')
            if not new_pass:
                mess.showerror('No Password', 'Password not set!')
                return False
            
            hashed = self.hash_password(new_pass)
            with open(password_file, "w") as f:
                f.write(hashed)
            mess.showinfo('Password Set', 'Password registered successfully!')
            return True

        with open(password_file, "r") as f:
            stored_hash = f.read().strip()

        password = tsd.askstring('Authentication', 'Enter Password:', show='*')
        if not password:
            return False

        if self.verify_password(password, stored_hash):
            return True
        else:
            mess.showerror('Authentication Failed', 'Incorrect password')
            return False

    def setup_academic_year(self):
        """Setup academic year configuration"""
        config_file = os.path.join("AcademicConfig", "academic_config.csv")
        
        # Check if config already exists
        if os.path.exists(config_file):
            try:
                df_config = pd.read_csv(config_file)
                if not df_config.empty:
                    return True
            except:
                pass
        
        # Create new academic year configuration
        setup_window = tk.Tk()
        setup_window.geometry("400x300")
        setup_window.title("Academic Year Setup")
        setup_window.configure(bg="white")
        
        tk.Label(setup_window, text="Academic Year Configuration", 
                bg="white", font=('Arial', 16, 'bold')).pack(pady=20)
        
        tk.Label(setup_window, text="Total Working Days in Academic Year:", 
                bg="white", font=('Arial', 12)).pack(pady=10)
        
        total_days_entry = tk.Entry(setup_window, width=20, font=('Arial', 12))
        total_days_entry.pack(pady=5)
        total_days_entry.insert(0, "200")  # Default value
        
        tk.Label(setup_window, text="Academic Year (e.g., 2024-25):", 
                bg="white", font=('Arial', 12)).pack(pady=10)
        
        year_entry = tk.Entry(setup_window, width=20, font=('Arial', 12))
        year_entry.pack(pady=5)
        year_entry.insert(0, f"{datetime.datetime.now().year}-{str(datetime.datetime.now().year + 1)[2:]}")
        
        def save_config():
            total_days = total_days_entry.get().strip()
            academic_year = year_entry.get().strip()
            
            if not total_days.isdigit() or int(total_days) < 1:
                mess.showerror("Invalid Input", "Please enter a valid number of working days")
                return
                
            if not academic_year:
                mess.showerror("Invalid Input", "Please enter academic year")
                return
            
            # Save configuration
            config_data = {
                'ACADEMIC_YEAR': [academic_year],
                'TOTAL_WORKING_DAYS': [int(total_days)],
                'START_DATE': [datetime.datetime.now().strftime('%d-%m-%Y')]
            }
            
            df_config = pd.DataFrame(config_data)
            df_config.to_csv(config_file, index=False)
            
            mess.showinfo("Success", f"Academic year configuration saved!\nYear: {academic_year}\nTotal Days: {total_days}")
            setup_window.destroy()
        
        tk.Button(setup_window, text="Save Configuration", command=save_config,
                 bg="#3498db", fg="white", font=('Arial', 12, 'bold')).pack(pady=20)
        
        tk.Button(setup_window, text="Cancel", command=setup_window.destroy,
                 bg="#e74c3c", fg="white", font=('Arial', 12, 'bold')).pack(pady=5)
        
        setup_window.mainloop()
        return os.path.exists(config_file)

    def get_academic_config(self):
        """Get academic year configuration"""
        config_file = os.path.join("AcademicConfig", "academic_config.csv")
        try:
            if os.path.exists(config_file):
                df_config = pd.read_csv(config_file)
                if not df_config.empty:
                    return {
                        'year': df_config.iloc[0]['ACADEMIC_YEAR'],
                        'total_days': int(df_config.iloc[0]['TOTAL_WORKING_DAYS']),
                        'start_date': df_config.iloc[0]['START_DATE']
                    }
        except:
            pass
        return None

    def clear_id_field(self):
        """Clear ID input field"""
        self.txt.delete(0, 'end')
        self.message1.configure(text="1) Take Images >>> 2) Save Profile")

    def clear_name_field(self):
        """Clear name input field"""
        self.txt2.delete(0, 'end')
        self.message1.configure(text="1) Take Images >>> 2) Save Profile")

    def take_images(self):
        """Capture training images for face recognition"""
        if not self.check_haarcascade_file():
            return

        student_id = self.txt.get().strip()
        name = self.txt2.get().strip()

        # Validate inputs
        valid, error_msg = self.validate_inputs(student_id, name)
        if not valid:
            mess.showerror('Invalid Input', error_msg)
            return

        # Check for duplicate ID
        details_file = os.path.join("StudentDetails", "StudentDetails.csv")
        if os.path.exists(details_file):
            df = pd.read_csv(details_file)
            if not df.empty and 'ID' in df.columns:
                if student_id in df['ID'].astype(str).values:
                    mess.showerror('Duplicate ID', f'Student with ID {student_id} already exists!')
                    return

        # Get academic configuration
        config = self.get_academic_config()
        if not config:
            if not self.setup_academic_year():
                mess.showerror('Configuration Required', 'Academic year configuration is required!')
                return
            config = self.get_academic_config()

        # Get next serial number
        serial = self.get_next_serial()

        try:
            # Initialize camera
            cam = cv2.VideoCapture(0)
            if not cam.isOpened():
                mess.showerror('Camera Error', 'Could not access camera')
                return

            detector = cv2.CascadeClassifier(HAAR_CASCADE_FILE)
            sample_num = 0
            
            mess.showinfo('Instructions', 'Position your face in the camera frame.\nPress "q" to stop early or wait for 100 samples.')

            while True:
                ret, img = cam.read()
                if not ret:
                    break

                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                faces = detector.detectMultiScale(gray, 1.3, 5, minSize=(30, 30))

                for (x, y, w, h) in faces:
                    cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 2)
                    sample_num += 1
                    
                    # Save face image
                    filename = f"TrainingImage/{name}.{serial}.{student_id}.{sample_num}.jpg"
                    cv2.imwrite(filename, gray[y:y + h, x:x + w])
                    
                    # Display progress
                    cv2.putText(img, f'Samples: {sample_num}/{MAX_SAMPLE_IMAGES}', 
                               (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

                cv2.imshow('Capturing Images', img)

                if cv2.waitKey(100) & 0xFF == ord('q'):
                    break
                elif sample_num >= MAX_SAMPLE_IMAGES:
                    break

        except Exception as e:
            logging.error(f"Error capturing images: {e}")
            mess.showerror('Error', f'Error capturing images: {str(e)}')
        finally:
            cam.release()
            cv2.destroyAllWindows()

        if sample_num > 0:
            # Save student details
            self.save_student_details(serial, student_id, name, config['total_days'])
            self.message1.configure(text=f"Images captured for ID: {student_id} ({sample_num} samples)")
            mess.showinfo('Success', f'Successfully captured {sample_num} images for {name}')
        else:
            mess.showerror('No Images', 'No face detected. Please try again.')

    def get_next_serial(self):
        """Get next serial number for student"""
        details_file = os.path.join("StudentDetails", "StudentDetails.csv")
        if not os.path.exists(details_file):
            return 1
        
        try:
            df = pd.read_csv(details_file)
            if df.empty:
                return 1
            return len(df) + 1
        except:
            return 1

    def save_student_details(self, serial, student_id, name, total_academic_days):
        """Save student details to CSV with academic information"""
        details_file = os.path.join("StudentDetails", "StudentDetails.csv")
        columns = ['SERIAL NO.', 'ID', 'NAME', 'REGISTRATION DATE', 'TOTAL_ACADEMIC_DAYS']
        
        registration_date = datetime.datetime.now().strftime('%d-%m-%Y')
        row = [serial, student_id, name, registration_date, total_academic_days]

        if not os.path.exists(details_file):
            df = pd.DataFrame([row], columns=columns)
        else:
            df = pd.read_csv(details_file)
            new_row = pd.DataFrame([row], columns=columns)
            df = pd.concat([df, new_row], ignore_index=True)
        
        df.to_csv(details_file, index=False)

    def train_images(self):
        """Train the face recognition model"""
        if not self.authenticate_user():
            return

        if not self.check_haarcascade_file():
            return

        try:
            recognizer = cv2.face.LBPHFaceRecognizer_create()
            faces, ids = self.get_images_and_labels("TrainingImage")
            
            if len(faces) == 0:
                mess.showerror('No Data', 'No training images found! Please register students first.')
                return

            recognizer.train(faces, np.array(ids))
            model_file = os.path.join("TrainingImageLabel", "Trainner.yml")
            recognizer.save(model_file)
            
            self.message1.configure(text="Profile saved successfully!")
            self.update_registration_count()
            mess.showinfo('Success', f'Model trained with {len(faces)} images from {len(set(ids))} students')
            
        except Exception as e:
            logging.error(f"Training error: {e}")
            mess.showerror('Training Error', f'Error during training: {str(e)}')

    def get_images_and_labels(self, path):
        """Load training images and extract labels"""
        if not os.path.exists(path):
            return [], []

        image_paths = [os.path.join(path, f) for f in os.listdir(path) if f.endswith(('.jpg', '.png'))]
        faces = []
        ids = []

        for image_path in image_paths:
            try:
                # Load image
                pil_image = Image.open(image_path).convert('L')
                image_np = np.array(pil_image, 'uint8')
                
                # Extract ID from filename
                filename = os.path.basename(image_path)
                parts = filename.split('.')
                if len(parts) >= 3:
                    student_id = int(parts[1])  # serial number for recognition
                    faces.append(image_np)
                    ids.append(student_id)
                    
            except Exception as e:
                logging.warning(f"Error processing {image_path}: {e}")
                continue

        return faces, ids

    def update_points(self, student_id, name):
        """Update attendance points for student"""
        points_file = os.path.join("StudentDetails", "StudentPoints.csv")
        student_id = str(student_id)

        try:
            if os.path.exists(points_file):
                df_points = pd.read_csv(points_file)
                if student_id in df_points['ID'].astype(str).values:
                    df_points.loc[df_points['ID'].astype(str) == student_id, 'POINTS'] += 1
                else:
                    new_row = pd.DataFrame([{'ID': student_id, 'NAME': name, 'POINTS': 1}])
                    df_points = pd.concat([df_points, new_row], ignore_index=True)
            else:
                df_points = pd.DataFrame([{'ID': student_id, 'NAME': name, 'POINTS': 1}])
            
            df_points.to_csv(points_file, index=False)
            
        except Exception as e:
            logging.error(f"Error updating points: {e}")

    def get_points(self, student_id):
        """Get points for a student"""
        points_file = os.path.join("StudentDetails", "StudentPoints.csv")
        student_id = str(student_id)
        
        try:
            if not os.path.exists(points_file):
                return 0
            df_points = pd.read_csv(points_file)
            if student_id not in df_points['ID'].astype(str).values:
                return 0
            return int(df_points.loc[df_points['ID'].astype(str) == student_id, 'POINTS'].values[0])
        except:
            return 0

    def calculate_attendance_percentage(self, student_id):
        """Calculate attendance percentage for a student"""
        # Get student details
        details_file = os.path.join("StudentDetails", "StudentDetails.csv")
        if not os.path.exists(details_file):
            return 0, 0, 0

        try:
            df_students = pd.read_csv(details_file)
            student_row = df_students[df_students['ID'].astype(str) == str(student_id)]
            
            if student_row.empty:
                return 0, 0, 0

            # Get total academic days
            total_academic_days = int(student_row.iloc[0]['TOTAL_ACADEMIC_DAYS'])
            
            # Count attendance days
            attended_days = 0
            attendance_dir = "Attendance"
            
            if os.path.exists(attendance_dir):
                for filename in os.listdir(attendance_dir):
                    if filename.startswith("Attendance_") and filename.endswith(".csv"):
                        try:
                            df_attendance = pd.read_csv(os.path.join(attendance_dir, filename))
                            if not df_attendance.empty and 'ID' in df_attendance.columns:
                                if str(student_id) in df_attendance['ID'].astype(str).values:
                                    attended_days += 1
                        except:
                            continue

            # Calculate percentage
            if total_academic_days > 0:
                percentage = (attended_days / total_academic_days) * 100
            else:
                percentage = 0

            return percentage, attended_days, total_academic_days
            
        except Exception as e:
            logging.error(f"Error calculating attendance percentage: {e}")
            return 0, 0, 0

    def determine_rewards(self, points, percentage):
        """Determine rewards based on points and percentage"""
        earned_rewards = []
        
        # Points-based rewards
        for threshold, reward in REWARDS.items():
            if threshold <= 50 and points >= threshold:  # Traditional point rewards
                earned_rewards.append(reward)
            elif threshold > 50 and percentage >= threshold:  # Percentage-based rewards
                earned_rewards.append(reward)
                
        return earned_rewards

    def generate_certificate(self, name, student_id, points, percentage):
        """Generate attendance certificate with percentage"""
        try:
            # Create certificate image
            img = Image.new('RGB', (800, 600), color='white')
            draw = ImageDraw.Draw(img)
            
            # Try to load a font, fallback to default if not available
            try:
                title_font = ImageFont.truetype("arial.ttf", 36)
                text_font = ImageFont.truetype("arial.ttf", 24)
                small_font = ImageFont.truetype("arial.ttf", 18)
            except:
                title_font = ImageFont.load_default()
                text_font = ImageFont.load_default()
                small_font = ImageFont.load_default()

            # Certificate design
            draw.rectangle([50, 50, 750, 550], outline='gold', width=3)
            draw.rectangle([70, 70, 730, 530], outline='darkblue', width=2)

            # Title
            draw.text((120, 100), "CERTIFICATE OF ATTENDANCE", fill='darkblue', font=title_font)
            
            # Content
            draw.text((200, 180), "This is to certify that", fill='black', font=text_font)
            draw.text((250, 220), name.upper(), fill='darkgreen', font=title_font)
            draw.text((280, 270), f"Student ID: {student_id}", fill='black', font=text_font)
            draw.text((100, 320), f"has achieved {percentage:.1f}% attendance", fill='black', font=text_font)
            draw.text((150, 350), f"with {points} attendance points", fill='black', font=text_font)
            
            # Performance message
            if percentage >= 90:
                performance_msg = "EXCELLENT ATTENDANCE RECORD"
                color = 'darkgreen'
            elif percentage >= 75:
                performance_msg = "GOOD ATTENDANCE RECORD"
                color = 'blue'
            else:
                performance_msg = "ATTENDANCE IMPROVEMENT NEEDED"
                color = 'red'
                
            draw.text((200, 390), performance_msg, fill=color, font=text_font)
            
            # Date and signature area
            date_str = datetime.datetime.now().strftime('%B %d, %Y')
            draw.text((100, 470), f"Date: {date_str}", fill='black', font=small_font)
            draw.text((500, 470), "Authorized Signature", fill='black', font=small_font)
            draw.line([500, 490, 650, 490], fill='black', width=2)

            # Save certificate
            cert_filename = f"Certificates/certificate_{student_id}_{datetime.datetime.now().strftime('%Y%m%d')}.png"
            img.save(cert_filename)
            mess.showinfo('Certificate Generated', f'Certificate saved as: {cert_filename}')
            
        except Exception as e:
            logging.error(f"Certificate generation error: {e}")
            mess.showerror('Error', f'Error generating certificate: {str(e)}')

    def view_student_stats(self):
        """View detailed statistics for a student"""
        student_id = tsd.askstring('View Student Stats', 'Enter Student Roll Number/ID:')
        if not student_id:
            return

        # Get student details
        details_file = os.path.join("StudentDetails", "StudentDetails.csv")
        if not os.path.exists(details_file):
            mess.showinfo('No Data', 'No student records available')
            return

        try:
            df_students = pd.read_csv(details_file)
            student_id = str(student_id)
            
            if student_id not in df_students['ID'].astype(str).values:
                mess.showinfo('No Record', f'No student found with ID: {student_id}')
                return

            student_row = df_students[df_students['ID'].astype(str) == student_id].iloc[0]
            name = student_row['NAME']
            
            # Calculate attendance statistics
            percentage, attended_days, total_academic_days = self.calculate_attendance_percentage(student_id)
            points = self.get_points(student_id)
            rewards = self.determine_rewards(points, percentage)

            # Create detailed stats window
            stats_window = tk.Tk()
            stats_window.geometry("500x400")
            stats_window.title(f"Student Statistics - {name}")
            stats_window.configure(bg="white")

            # Title
            tk.Label(stats_window, text=f"Student Statistics", 
                    bg="white", fg="#2c3e50", font=('Arial', 18, 'bold')).pack(pady=10)

            # Student info frame
            info_frame = tk.Frame(stats_window, bg="#ecf0f1", relief='raised', bd=2)
            info_frame.pack(pady=10, padx=20, fill='x')

            tk.Label(info_frame, text=f"Name: {name}", 
                    bg="#ecf0f1", font=('Arial', 12, 'bold')).pack(anchor='w', padx=10, pady=2)
            tk.Label(info_frame, text=f"Roll Number: {student_id}", 
                    bg="#ecf0f1", font=('Arial', 12, 'bold')).pack(anchor='w', padx=10, pady=2)

            # Attendance frame
            att_frame = tk.Frame(stats_window, bg="#e8f5e8", relief='raised', bd=2)
            att_frame.pack(pady=10, padx=20, fill='x')

            tk.Label(att_frame, text="ATTENDANCE DETAILS", 
                    bg="#e8f5e8", fg="#27ae60", font=('Arial', 14, 'bold')).pack(pady=5)
            tk.Label(att_frame, text=f"Days Attended: {attended_days}", 
                    bg="#e8f5e8", font=('Arial', 11)).pack(anchor='w', padx=10)
            tk.Label(att_frame, text=f"Total Academic Days: {total_academic_days}", 
                    bg="#e8f5e8", font=('Arial', 11)).pack(anchor='w', padx=10)
            
            # Attendance percentage with color coding
            percentage_color = "#27ae60" if percentage >= 75 else "#e74c3c"
            tk.Label(att_frame, text=f"Attendance Percentage: {percentage:.1f}%", 
                    bg="#e8f5e8", fg=percentage_color, font=('Arial', 12, 'bold')).pack(anchor='w', padx=10, pady=2)
            
            # Status
            if percentage < DETAINED_THRESHOLD:
                status = "DETAINED (Below 60%)"
                status_color = "#e74c3c"
            elif percentage < MINIMUM_ATTENDANCE_PERCENTAGE:
                status = "LOW ATTENDANCE (Below 75%)"
                status_color = "#f39c12"
            else:
                status = "GOOD STANDING"
                status_color = "#27ae60"
                
            tk.Label(att_frame, text=f"Status: {status}", 
                    bg="#e8f5e8", fg=status_color, font=('Arial', 11, 'bold')).pack(anchor='w', padx=10, pady=2)

            # Points and rewards frame
            reward_frame = tk.Frame(stats_window, bg="#fff3cd", relief='raised', bd=2)
            reward_frame.pack(pady=10, padx=20, fill='x')

            tk.Label(reward_frame, text="REWARDS & POINTS", 
                    bg="#fff3cd", fg="#856404", font=('Arial', 14, 'bold')).pack(pady=5)
            tk.Label(reward_frame, text=f"Attendance Points: {points}", 
                    bg="#fff3cd", font=('Arial', 11, 'bold')).pack(anchor='w', padx=10)

            reward_text = '\n'.join(rewards) if rewards else 'No rewards earned yet'
            tk.Label(reward_frame, text=f"Earned Rewards:\n{reward_text}", 
                    bg="#fff3cd", font=('Arial', 10), justify='left').pack(anchor='w', padx=10, pady=5)

            # Buttons frame
            btn_frame = tk.Frame(stats_window, bg="white")
            btn_frame.pack(pady=20)

            if "Attendance Certificate" in rewards or percentage >= 75:
                tk.Button(btn_frame, text="Generate Certificate", 
                         command=lambda: self.generate_certificate(name, student_id, points, percentage),
                         bg="#3498db", fg="white", font=('Arial', 10, 'bold')).pack(side='left', padx=5)

            tk.Button(btn_frame, text="Close", command=stats_window.destroy,
                     bg="#95a5a6", fg="white", font=('Arial', 10, 'bold')).pack(side='left', padx=5)

            stats_window.mainloop()

        except Exception as e:
            logging.error(f"Error viewing student stats: {e}")
            mess.showerror('Error', f'Error retrieving student statistics: {str(e)}')

    def view_rewards(self):
        """View rewards for a student (legacy function - now calls view_student_stats)"""
        self.view_student_stats()

    def view_detained_students(self):
        """View list of students with attendance below detention threshold"""
        details_file = os.path.join("StudentDetails", "StudentDetails.csv")
        if not os.path.exists(details_file):
            mess.showinfo('No Data', 'No student records available')
            return

        try:
            df_students = pd.read_csv(details_file)
            if df_students.empty:
                mess.showinfo('No Data', 'No student records found')
                return

            # Create detained students window
            detained_window = tk.Tk()
            detained_window.geometry("800x600")
            detained_window.title("Detained Students List (Below 60% Attendance)")
            detained_window.configure(bg="white")

            # Title
            title_frame = tk.Frame(detained_window, bg="#e74c3c")
            title_frame.pack(fill='x', pady=(0, 10))
            
            tk.Label(title_frame, text="DETAINED STUDENTS LIST", 
                    bg="#e74c3c", fg="white", font=('Arial', 18, 'bold')).pack(pady=10)
            tk.Label(title_frame, text="Students with attendance below 60%", 
                    bg="#e74c3c", fg="white", font=('Arial', 12)).pack(pady=(0, 10))

            # Create treeview for detained students
            tree_frame = tk.Frame(detained_window)
            tree_frame.pack(pady=10, padx=20, fill='both', expand=True)

            columns = ('ID', 'Name', 'Attended', 'Total', 'Percentage', 'Status')
            detained_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

            # Configure columns
            detained_tree.column('ID', width=80, anchor='center')
            detained_tree.column('Name', width=150, anchor='w')
            detained_tree.column('Attended', width=80, anchor='center')
            detained_tree.column('Total', width=80, anchor='center')
            detained_tree.column('Percentage', width=100, anchor='center')
            detained_tree.column('Status', width=120, anchor='center')

            # Configure headings
            detained_tree.heading('ID', text='Roll No.')
            detained_tree.heading('Name', text='Student Name')
            detained_tree.heading('Attended', text='Days Attended')
            detained_tree.heading('Total', text='Total Days')
            detained_tree.heading('Percentage', text='Attendance %')
            detained_tree.heading('Status', text='Status')

            # Scrollbar
            scrollbar_detained = ttk.Scrollbar(tree_frame, orient='vertical', command=detained_tree.yview)
            detained_tree.configure(yscrollcommand=scrollbar_detained.set)

            # Pack treeview and scrollbar
            detained_tree.pack(side='left', fill='both', expand=True)
            scrollbar_detained.pack(side='right', fill='y')

            # Collect detained students data
            detained_students = []
            total_students = 0
            
            for _, student in df_students.iterrows():
                student_id = str(student['ID'])
                name = student['NAME']
                
                percentage, attended_days, total_academic_days = self.calculate_attendance_percentage(student_id)
                total_students += 1
                
                status = ""
                if percentage < DETAINED_THRESHOLD:
                    status = "DETAINED"
                    detained_students.append({
                        'id': student_id,
                        'name': name,
                        'attended': attended_days,
                        'total': total_academic_days,
                        'percentage': percentage,
                        'status': status
                    })
                elif percentage < MINIMUM_ATTENDANCE_PERCENTAGE:
                    status = "AT RISK"
                    detained_students.append({
                        'id': student_id,
                        'name': name,
                        'attended': attended_days,
                        'total': total_academic_days,
                        'percentage': percentage,
                        'status': status
                    })

            # Sort by percentage (lowest first)
            detained_students.sort(key=lambda x: x['percentage'])

            # Insert data into treeview
            for student in detained_students:
                if student['status'] == "DETAINED":
                    tags = ('detained',)
                else:
                    tags = ('at_risk',)
                    
                detained_tree.insert('', 'end', 
                                   values=(student['id'], student['name'], 
                                          student['attended'], student['total'],
                                          f"{student['percentage']:.1f}%", student['status']),
                                   tags=tags)

            # Configure tags for color coding
            detained_tree.tag_configure('detained', background='#ffebee', foreground='#c62828')
            detained_tree.tag_configure('at_risk', background='#fff3e0', foreground='#ef6c00')

            # Statistics frame
            stats_frame = tk.Frame(detained_window, bg="#f8f9fa", relief='raised', bd=2)
            stats_frame.pack(pady=10, padx=20, fill='x')

            detained_count = len([s for s in detained_students if s['status'] == "DETAINED"])
            at_risk_count = len([s for s in detained_students if s['status'] == "AT RISK"])

            tk.Label(stats_frame, text="SUMMARY STATISTICS", 
                    bg="#f8f9fa", fg="#2c3e50", font=('Arial', 14, 'bold')).pack(pady=5)
            
            summary_text = f"Total Students: {total_students} | Detained Students: {detained_count} | At Risk Students: {at_risk_count}"
            tk.Label(stats_frame, text=summary_text, 
                    bg="#f8f9fa", fg="#2c3e50", font=('Arial', 11)).pack(pady=5)

            # Buttons frame
            btn_frame = tk.Frame(detained_window, bg="white")
            btn_frame.pack(pady=10)

            def export_detained_list():
                """Export detained students list to CSV"""
                try:
                    if detained_students:
                        df_detained = pd.DataFrame(detained_students)
                        filename = f"Detained_Students_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                        df_detained.to_csv(filename, index=False)
                        mess.showinfo('Export Success', f'Detained students list exported to: {filename}')
                    else:
                        mess.showinfo('No Data', 'No detained students to export')
                except Exception as e:
                    mess.showerror('Export Error', f'Error exporting data: {str(e)}')

            def send_notifications():
                """Simulate sending notifications to detained students"""
                detained_count = len([s for s in detained_students if s['status'] == "DETAINED"])
                if detained_count > 0:
                    mess.showinfo('Notifications', f'Notification sent to {detained_count} detained students and their parents/guardians.')
                else:
                    mess.showinfo('No Notifications', 'No detained students found to notify.')

            tk.Button(btn_frame, text="Export List", command=export_detained_list,
                     bg="#17a2b8", fg="white", font=('Arial', 10, 'bold')).pack(side='left', padx=5)
            
            tk.Button(btn_frame, text="Send Notifications", command=send_notifications,
                     bg="#ffc107", fg="black", font=('Arial', 10, 'bold')).pack(side='left', padx=5)
            
            tk.Button(btn_frame, text="Close", command=detained_window.destroy,
                     bg="#6c757d", fg="white", font=('Arial', 10, 'bold')).pack(side='left', padx=5)

            if not detained_students:
                # Show message if no detained students
                tk.Label(tree_frame, text="No detained students found!\nAll students have good attendance.", 
                        font=('Arial', 16), fg="#27ae60", bg="white").pack(expand=True)

            detained_window.mainloop()

        except Exception as e:
            logging.error(f"Error viewing detained students: {e}")
            mess.showerror('Error', f'Error retrieving detained students list: {str(e)}')

    def track_attendance(self):
        """Track attendance using face recognition"""
        if not self.check_haarcascade_file():
            return

        # Clear previous attendance display
        for item in self.tv.get_children():
            self.tv.delete(item)

        # Load trained model
        model_file = os.path.join("TrainingImageLabel", "Trainner.yml")
        if not os.path.exists(model_file):
            mess.showerror('Model Missing', 'No trained model found! Please train the model first.')
            return

        # Load student details
        details_file = os.path.join("StudentDetails", "StudentDetails.csv")
        if not os.path.exists(details_file):
            mess.showerror('No Students', 'No student records found! Please register students first.')
            return

        try:
            recognizer = cv2.face.LBPHFaceRecognizer_create()
            recognizer.read(model_file)
            face_cascade = cv2.CascadeClassifier(HAAR_CASCADE_FILE)
            df_students = pd.read_csv(details_file)

            cam = cv2.VideoCapture(0)
            if not cam.isOpened():
                mess.showerror('Camera Error', 'Could not access camera')
                return

            recognized_students = set()
            font = cv2.FONT_HERSHEY_SIMPLEX
            
            mess.showinfo('Instructions', 'Position your face in the camera frame.\nPress "q" to quit.')

            while True:
                ret, frame = cam.read()
                if not ret:
                    break

                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = face_cascade.detectMultiScale(gray, 1.2, 5, minSize=(30, 30))

                for (x, y, w, h) in faces:
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                    
                    try:
                        serial, confidence = recognizer.predict(gray[y:y + h, x:x + w])
                        
                        if confidence < MIN_CONFIDENCE:
                            # Find student by serial number
                            student_row = df_students[df_students['SERIAL NO.'] == serial]
                            if not student_row.empty:
                                name = student_row.iloc[0]['NAME']
                                student_id = str(student_row.iloc[0]['ID'])
                                
                                # Mark attendance if not already marked today
                                if student_id not in recognized_students:
                                    if self.mark_attendance(student_id, name):
                                        recognized_students.add(student_id)
                                        
                                        # Calculate updated percentage
                                        percentage, _, _ = self.calculate_attendance_percentage(student_id)
                                        
                                        mess.showinfo('Attendance Marked', 
                                                     f'Attendance marked for {name} (ID: {student_id})\nCurrent Attendance: {percentage:.1f}%')
                                
                                display_text = f"{name} ({confidence:.1f})"
                            else:
                                display_text = "Unknown"
                        else:
                            display_text = "Unknown"
                            
                    except Exception as e:
                        logging.warning(f"Recognition error: {e}")
                        display_text = "Unknown"
                    
                    cv2.putText(frame, display_text, (x, y - 10), font, 0.8, (0, 255, 0), 2)

                cv2.imshow('Attendance Tracking', frame)
                
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

        except Exception as e:
            logging.error(f"Attendance tracking error: {e}")
            mess.showerror('Error', f'Error during attendance tracking: {str(e)}')
        finally:
            cam.release()
            cv2.destroyAllWindows()

        # Refresh attendance display
        self.load_today_attendance()

    def mark_attendance(self, student_id, name):
        """Mark attendance for a student"""
        today = datetime.datetime.now().strftime('%d-%m-%Y')
        attendance_file = os.path.join("Attendance", f"Attendance_{today}.csv")
        
        # Check if already marked today
        if os.path.exists(attendance_file):
            try:
                df_att = pd.read_csv(attendance_file)
                if not df_att.empty and 'ID' in df_att.columns:
                    if student_id in df_att['ID'].astype(str).values:
                        return False  # Already marked
            except:
                pass

        # Mark new attendance
        timestamp = datetime.datetime.now().strftime('%H:%M:%S')
        columns = ['ID', 'NAME', 'DATE', 'TIME']
        attendance_record = [student_id, name, today, timestamp]

        try:
            if os.path.exists(attendance_file):
                df_att = pd.read_csv(attendance_file)
                new_record = pd.DataFrame([attendance_record], columns=columns)
                df_att = pd.concat([df_att, new_record], ignore_index=True)
            else:
                df_att = pd.DataFrame([attendance_record], columns=columns)
            
            df_att.to_csv(attendance_file, index=False)
            
            # Update points
            self.update_points(student_id, name)
            return True
            
        except Exception as e:
            logging.error(f"Error marking attendance: {e}")
            return False

    def load_today_attendance(self):
        """Load and display today's attendance"""
        today = datetime.datetime.now().strftime('%d-%m-%Y')
        attendance_file = os.path.join("Attendance", f"Attendance_{today}.csv")
        
        # Clear existing items
        for item in self.tv.get_children():
            self.tv.delete(item)

        if not os.path.exists(attendance_file):
            return

        try:
            df = pd.read_csv(attendance_file)
            for _, row in df.iterrows():
                self.tv.insert('', 0, text=str(row['ID']), 
                             values=(str(row['NAME']), str(row['DATE']), str(row['TIME'])))
        except Exception as e:
            logging.error(f"Error loading attendance: {e}")

    def update_registration_count(self):
        """Update registration count display"""
        details_file = os.path.join("StudentDetails", "StudentDetails.csv")
        try:
            if os.path.exists(details_file):
                df = pd.read_csv(details_file)
                count = len(df) if not df.empty else 0
            else:
                count = 0
            self.message.configure(text=f'Total Registrations: {count}')
        except:
            self.message.configure(text='Total Registrations: 0')

    def configure_academic_year(self):
        """Allow reconfiguration of academic year settings"""
        config_file = os.path.join("AcademicConfig", "academic_config.csv")
        
        # Get current configuration
        current_config = self.get_academic_config()
        
        config_window = tk.Tk()
        config_window.geometry("450x350")
        config_window.title("Academic Year Configuration")
        config_window.configure(bg="white")
        
        tk.Label(config_window, text="Academic Year Configuration", 
                bg="white", font=('Arial', 16, 'bold')).pack(pady=20)
        
        # Current settings display
        if current_config:
            current_frame = tk.Frame(config_window, bg="#e8f5e8", relief='raised', bd=2)
            current_frame.pack(pady=10, padx=20, fill='x')
            
            tk.Label(current_frame, text="Current Settings:", 
                    bg="#e8f5e8", font=('Arial', 12, 'bold')).pack(pady=5)
            tk.Label(current_frame, text=f"Academic Year: {current_config['year']}", 
                    bg="#e8f5e8", font=('Arial', 10)).pack(anchor='w', padx=10)
            tk.Label(current_frame, text=f"Total Working Days: {current_config['total_days']}", 
                    bg="#e8f5e8", font=('Arial', 10)).pack(anchor='w', padx=10)
        
        # New settings
        tk.Label(config_window, text="New Academic Year:", 
                bg="white", font=('Arial', 12)).pack(pady=(20, 5))
        
        year_entry = tk.Entry(config_window, width=20, font=('Arial', 12))
        year_entry.pack(pady=5)
        if current_config:
            year_entry.insert(0, current_config['year'])
        
        tk.Label(config_window, text="Total Working Days:", 
                bg="white", font=('Arial', 12)).pack(pady=(10, 5))
        
        days_entry = tk.Entry(config_window, width=20, font=('Arial', 12))
        days_entry.pack(pady=5)
        if current_config:
            days_entry.insert(0, str(current_config['total_days']))
        
        def save_new_config():
            new_year = year_entry.get().strip()
            new_days = days_entry.get().strip()
            
            if not new_year:
                mess.showerror("Invalid Input", "Please enter academic year")
                return
                
            if not new_days.isdigit() or int(new_days) < 1:
                mess.showerror("Invalid Input", "Please enter valid number of working days")
                return
            
            # Save new configuration
            config_data = {
                'ACADEMIC_YEAR': [new_year],
                'TOTAL_WORKING_DAYS': [int(new_days)],
                'START_DATE': [datetime.datetime.now().strftime('%d-%m-%Y')]
            }
            
            df_config = pd.DataFrame(config_data)
            df_config.to_csv(config_file, index=False)
            
            mess.showinfo("Success", f"Academic configuration updated!\nYear: {new_year}\nTotal Days: {new_days}")
            config_window.destroy()
        
        # Buttons
        btn_frame = tk.Frame(config_window, bg="white")
        btn_frame.pack(pady=20)
        
        tk.Button(btn_frame, text="Save Configuration", command=save_new_config,
                 bg="#3498db", fg="white", font=('Arial', 12, 'bold')).pack(side='left', padx=10)
        
        tk.Button(btn_frame, text="Cancel", command=config_window.destroy,
                 bg="#95a5a6", fg="white", font=('Arial', 12, 'bold')).pack(side='left', padx=10)
        
        config_window.mainloop()

    def init_gui(self):
        """Initialize the GUI"""
        # Main window
        self.window = tk.Tk()
        self.window.geometry("1280x720")
        self.window.resizable(True, False)
        self.window.title("Smart Attendance System with Facial Recognition")
        self.window.configure(background='#2c3e50')

        # Date and time setup
        now = datetime.datetime.now()
        day = now.strftime('%d')
        month = now.strftime('%m')
        year = now.strftime('%Y')
        
        month_names = {
            '01': 'January', '02': 'February', '03': 'March', '04': 'April',
            '05': 'May', '06': 'June', '07': 'July', '08': 'August',
            '09': 'September', '10': 'October', '11': 'November', '12': 'December'
        }

        # Title
        title_label = tk.Label(self.window, 
                              text="Smart Attendance Monitoring with Facial Recognition",
                              fg="white", bg="#2c3e50", font=('Arial', 24, 'bold'))
        title_label.place(x=50, y=20)

        # Date and time frames
        date_frame = tk.Frame(self.window, bg="#34495e")
        date_frame.place(relx=0.35, rely=0.08, relwidth=0.20, relheight=0.06)
        
        time_frame = tk.Frame(self.window, bg="#34495e") 
        time_frame.place(relx=0.56, rely=0.08, relwidth=0.12, relheight=0.06)

        # Date display
        date_label = tk.Label(date_frame, 
                             text=f"{day}-{month_names[month]}-{year}",
                             fg="#ecf0f1", bg="#34495e", font=('Arial', 16, 'bold'))
        date_label.pack(fill='both', expand=1)

        # Clock
        self.clock = tk.Label(time_frame, fg="#ecf0f1", bg="#34495e", 
                             font=('Arial', 16, 'bold'))
        self.clock.pack(fill='both', expand=1)
        self.tick()

        # Main frames
        self.frame1 = tk.Frame(self.window, bg="#ecf0f1")  # Attendance frame
        self.frame1.place(relx=0.05, rely=0.16, relwidth=0.42, relheight=0.80)

        self.frame2 = tk.Frame(self.window, bg="#ecf0f1")  # Registration frame
        self.frame2.place(relx=0.53, rely=0.16, relwidth=0.42, relheight=0.80)

        # Frame headers
        header1 = tk.Label(self.frame1, text="ATTENDANCE TRACKING", 
                          fg="white", bg="#27ae60", font=('Arial', 16, 'bold'))
        header1.pack(fill='x', pady=(0, 10))

        header2 = tk.Label(self.frame2, text="STUDENT REGISTRATION", 
                          fg="white", bg="#3498db", font=('Arial', 16, 'bold'))
        header2.pack(fill='x', pady=(0, 10))

        # Registration form elements
        tk.Label(self.frame2, text="Student Roll No./ID:", bg="#ecf0f1", 
                font=('Arial', 14, 'bold')).place(x=50, y=60)
        self.txt = tk.Entry(self.frame2, width=25, font=('Arial', 12))
        self.txt.place(x=50, y=90)

        tk.Label(self.frame2, text="Student Name:", bg="#ecf0f1", 
                font=('Arial', 14, 'bold')).place(x=50, y=130)
        self.txt2 = tk.Entry(self.frame2, width=25, font=('Arial', 12))
        self.txt2.place(x=50, y=160)

        # Clear buttons
        clear_id_btn = tk.Button(self.frame2, text="Clear", command=self.clear_id_field,
                                fg="white", bg="#e74c3c", width=8, font=('Arial', 10, 'bold'))
        clear_id_btn.place(x=300, y=88)

        clear_name_btn = tk.Button(self.frame2, text="Clear", command=self.clear_name_field,
                                  fg="white", bg="#e74c3c", width=8, font=('Arial', 10, 'bold'))
        clear_name_btn.place(x=300, y=158)

        # Action buttons for registration
        take_images_btn = tk.Button(self.frame2, text="Take Images", command=self.take_images,
                                   fg="white", bg="#9b59b6", width=30, height=2,
                                   font=('Arial', 12, 'bold'))
        take_images_btn.place(x=50, y=220)

        train_model_btn = tk.Button(self.frame2, text="Save Profile (Train Model)", 
                                   command=self.train_images, fg="white", bg="#9b59b6",
                                   width=30, height=2, font=('Arial', 12, 'bold'))
        train_model_btn.place(x=50, y=280)

        # Status messages
        self.message1 = tk.Label(self.frame2, text="1) Take Images >>> 2) Save Profile",
                                bg="#ecf0f1", fg="#2c3e50", font=('Arial', 12, 'italic'))
        self.message1.place(x=50, y=340)

        self.message = tk.Label(self.frame2, text="", bg="#ecf0f1", fg="#2c3e50",
                               font=('Arial', 11, 'bold'))
        self.message.place(x=50, y=480)

        # Attendance tracking buttons
        track_btn = tk.Button(self.frame1, text="Take Attendance", command=self.track_attendance,
                             fg="white", bg="#27ae60", width=30, height=2,
                             font=('Arial', 12, 'bold'))
        track_btn.place(x=50, y=50)

        # Updated rewards button (now shows detailed stats)
        stats_btn = tk.Button(self.frame1, text="View Student Statistics", 
                               command=self.view_student_stats, fg="white", bg="#f39c12",
                               width=30, height=2, font=('Arial', 12, 'bold'))
        stats_btn.place(x=50, y=120)

        # NEW: Detained Students List Button
        detained_btn = tk.Button(self.frame1, text="Detained Students List", 
                                command=self.view_detained_students, fg="white", bg="#e74c3c",
                                width=30, height=2, font=('Arial', 12, 'bold'))
        detained_btn.place(x=50, y=190)

        # Attendance table (moved down to accommodate new button)
        self.tv = ttk.Treeview(self.frame1, height=12, columns=('name', 'date', 'time'))
        self.tv.column('#0', width=100, anchor='center')
        self.tv.column('name', width=150, anchor='center')
        self.tv.column('date', width=120, anchor='center')
        self.tv.column('time', width=120, anchor='center')
        
        self.tv.heading('#0', text='Student ID')
        self.tv.heading('name', text='Name')
        self.tv.heading('date', text='Date')
        self.tv.heading('time', text='Time')
        
        self.tv.place(x=20, y=260)

        # Scrollbar for table
        scrollbar = ttk.Scrollbar(self.frame1, orient='vertical', command=self.tv.yview)
        scrollbar.place(x=490, y=260, height=300)
        self.tv.configure(yscrollcommand=scrollbar.set)

        # Menu bar
        menubar = tk.Menu(self.window)
        
        # Settings menu
        settings_menu = tk.Menu(menubar, tearoff=0)
        settings_menu.add_command(label='Change Password', command=self.change_password)
        settings_menu.add_separator()
        settings_menu.add_command(label='Configure Academic Year', command=self.configure_academic_year)
        settings_menu.add_command(label='Contact Us', command=self.contact)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label='About', command=lambda: mess.showinfo('About', 
                             'Smart Attendance System v2.0\nDeveloped with Facial Recognition Technology'))
        
        # Add menus to menubar
        menubar.add_cascade(label='Settings', menu=settings_menu)
        menubar.add_cascade(label='Help', menu=help_menu)
        
        # ...existing code...

        # Add menus to menubar
        menubar.add_cascade(label='Settings', menu=settings_menu)
        menubar.add_cascade(label='Help', menu=help_menu)

        # Set the menu bar
        self.window.config(menu=menubar)

        # Load today's attendance on startup
        self.load_today_attendance()

# Start the application
if __name__ == "__main__":
    AttendanceSystem().window.mainloop()