import firebase_admin
from firebase_admin import credentials, firestore
from shapely.geometry import Point, Polygon
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
import os
from dotenv import load_dotenv
from datetime import datetime
import json

# Load environment variables from .env file
load_dotenv()

# Initialize Firebase (if not already initialized)
try:
    firebase_admin.get_app()
except ValueError:
    cred = credentials.Certificate("/workspaces/urbanTrustApi/serviceAccountKey.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

class WardNotificationSystem:
    def __init__(self):
        """Initialize the Ward Notification System"""
        self.db = db
        
        # Email configuration
        self.email_sender = os.getenv("EMAIL_SENDER")
        self.email_password = os.getenv("EMAIL_PASSWORD")
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))

    def setup_ward_collection(self):
        """ Create the wards collection with sample data if it doesn't exist.
            Each ward document will have:
            - ward_id: unique identifier
            - name: name of the ward
            - officer_email: email of officer responsible
            - boundaries: array of coordinate objects defining ward polygon
            - area_sq_meters: area covered by the ward
        """
        # Using 'ward' collection name as specified
        wards_ref = self.db.collection('ward')
        
        # Check if wards collection is empty
        wards = list(wards_ref.limit(1).stream())
        if not wards:
            # Add sample wards
            sample_wards = [
                {
                    'ward_id': 'ward001',
                    'name': 'Central Ward',
                    'officer_email': 'aryaniaf2608@gmail.com',
                    'boundaries': [
                        {'lat': 12.9716, 'lng': 77.5946},
                        {'lat': 12.9796, 'lng': 77.5946},
                        {'lat': 12.9796, 'lng': 77.6046},
                        {'lat': 12.9716, 'lng': 77.6046}
                    ],
                    'area_sq_meters': 120000
                },
                {
                    'ward_id': 'ward002',
                    'name': 'North Ward',
                    'officer_email': 'nikhilrrvk@gmail.com',
                    'boundaries': [
                        {'lat': 13.0016, 'lng': 77.5946},
                        {'lat': 13.0096, 'lng': 77.5946},
                        {'lat': 13.0096, 'lng': 77.6046},
                        {'lat': 13.0016, 'lng': 77.6046}
                    ],
                    'area_sq_meters': 140000
                }
            ]
            
            for ward in sample_wards:
                wards_ref.document(ward['ward_id']).set(ward)
            
            print(f"Created {len(sample_wards)} sample wards in database")
        else:
            print("Wards collection already exists")

    def point_in_polygon(self, lat, long, boundaries):
        """
        Check if a point (lat, long) falls inside a polygon defined by boundaries
        
        Args:
            lat (float): Latitude of the point
            long (float): Longitude of the point
            boundaries (list): List of coordinate objects defining the polygon
            
        Returns:
            bool: True if point is inside polygon, False otherwise
        """
        point = Point(lat, long)
        # Convert boundaries to the format expected by Shapely
        polygon_coords = [(b['lat'], b['lng']) for b in boundaries]
        polygon = Polygon(polygon_coords)
        
        return polygon.contains(point)

    def find_ward_for_location(self, lat, long):
        """
        Find the ward for the given coordinates
        
        Args:
            lat (float): Latitude of the issue
            long (float): Longitude of the issue
            
        Returns:
            dict: Ward document or None if no ward contains the point
        """
        # Using 'ward' collection name as specified
        wards_ref = self.db.collection('ward')
        wards = list(wards_ref.stream())
        
        if not wards:
            print("No wards found in database")
            return None
        
        # FIXED: Actually check each ward to see if the point is within its boundaries
        for ward_doc in wards:
            ward = ward_doc.to_dict()
            ward['id'] = ward_doc.id
            
            # Check if the issue location is within this ward's boundaries
            if 'boundaries' in ward and self.point_in_polygon(lat, long, ward['boundaries']):
                print(f"Found matching ward: {ward['name']} for location ({lat}, {long})")
                return ward
        
        # If we get here, the point wasn't in any ward
        print(f"No ward contains the point ({lat}, {long})")
        return None

    def send_email_notification(self, officer_email, issue_data, ward_data):
        """
        Send email notification to ward officer
        
        Args:
            officer_email (str): Email address of ward officer
            issue_data (dict): Issue details
            ward_data (dict): Ward details
        """
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_sender
            msg['To'] = officer_email
            msg['Subject'] = f"New Issue Reported in {ward_data['name']} - {issue_data['category']}"
            
            # Format the email body
            body = f"""
            <html>
            <body>
                <h2>New Issue Reported in Your Ward</h2>
                <p><strong>Ward:</strong> {ward_data['name']} (ID: {ward_data['ward_id']})</p>
                <p><strong>Category:</strong> {issue_data['category']}</p>
                <p><strong>Description:</strong> {issue_data['description']}</p>
                <p><strong>Location:</strong> {issue_data['latitude']}, {issue_data['longitude']}</p>
                <p><strong>Reported on:</strong> {issue_data['created_at'].strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p><strong>Issue ID:</strong> {issue_data['id']}</p>
                <p>Please check the admin dashboard for more details.</p>
            </body>
            </html>
            """
            
            msg.attach(MIMEText(body, 'html'))
            
            # FIXED: Added debug print to verify email credentials
            print(f"Attempting to send email using: {self.smtp_server}:{self.smtp_port}")
            print(f"Sender: {self.email_sender}")
            print(f"Recipient: {officer_email}")
            
            # Connect to SMTP server and send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_sender, self.email_password)
                server.send_message(msg)
                
            print(f"Email notification sent to {officer_email}")
            return True
        
        except Exception as e:
            print(f"Failed to send email: {str(e)}")
            return False

    def process_new_issue(self, issue_id):
        """
        Process a newly created issue to send notifications
        
        Args:
            issue_id (str): ID of the newly created issue
        """
        try:
            # Get issue data
            issue_ref = self.db.collection('issues').document(issue_id)
            issue_doc = issue_ref.get()
            
            if not issue_doc.exists:
                print(f"Issue {issue_id} not found")
                return False
            
            issue_data = issue_doc.to_dict()
            issue_data['id'] = issue_id
            
            # FIXED: Added debug print to verify coordinates
            print(f"Processing issue at location: {issue_data['latitude']}, {issue_data['longitude']}")
            
            # Find ward for issue location
            ward = self.find_ward_for_location(
                float(issue_data['latitude']), 
                float(issue_data['longitude'])
            )
            
            if not ward:
                print(f"No ward found for location: {issue_data['latitude']}, {issue_data['longitude']}")
                # Update the issue with no assigned ward
                issue_ref.update({
                    'ward_assigned': False,
                    'notification_sent': False
                })
                return False
            
            # Update issue with ward info
            issue_ref.update({
                'ward_id': ward['ward_id'],
                'ward_name': ward['name'],
                'ward_assigned': True
            })
            
            # Send email notification
            email_sent = self.send_email_notification(ward['officer_email'], issue_data, ward)
            
            # Update issue with notification status
            issue_ref.update({
                'notification_sent': email_sent,
                'notification_email_sent': email_sent,
                'notification_time': firestore.SERVER_TIMESTAMP
            })
            
            return True
            
        except Exception as e:
            print(f"Error processing issue {issue_id}: {str(e)}")
            return False

    def setup_firestore_trigger(self):
        """
        Note: This is a conceptual function to explain how to set up a Firestore trigger.
        In practice, this would be implemented as a Cloud Function in Firebase.
        
        For a complete solution, you would:
        1. Create a Cloud Function in Firebase that triggers on issue creation
        2. The function would call process_new_issue() with the new issue ID
        """
        print("""
        ----------------------------------------------------------------
        To implement the Firestore trigger in a real application:
        
        1. Create a Cloud Function in Firebase with this code:
        
        exports.processNewIssue = functions.firestore
            .document('issues/{issueId}')
            .onCreate((snapshot, context) => {
                const issueId = context.params.issueId;
                const issueData = snapshot.data();
                
                // Call your Python API endpoint to process the issue
                // Or implement the processing logic directly in Node.js
            });
            
        2. Or use Firebase Admin SDK and set up a listener:
        
        db.collection('issues').onSnapshot(snapshot => {
            snapshot.docChanges().forEach(change => {
                if (change.type === 'added') {
                    const issueId = change.doc.id;
                    // Process the new issue
                }
            });
        });
        ----------------------------------------------------------------
        """)

    def test_with_sample_issue(self):
        """
        Test the notification system with a sample issue
        """
        # FIXED: Create a sample issue with coordinates that definitely match a ward's boundaries
        issue_data = {
            # These coordinates are inside the Central Ward boundaries
            'latitude': 12.9756,
            'longitude': 77.5996,
            'category': 'Road Damage',
            'category_kannada': 'ರಸ್ತೆ ಹಾನಿ',
            'description': 'Large pothole causing traffic issues',
            'description_kannada': 'ದೊಡ್ಡ ಗುಂಡಿ ಟ್ರಾಫಿಕ್ ಸಮಸ್ಯೆಗಳನ್ನು ಉಂಟುಮಾಡುತ್ತಿದೆ',
            'status': 'open',
            'created_at': datetime.now(),
            'image': '/workspaces/urbanTrustApi/new_pothole.JPG',
            'similar_count': 0
        }
        
        # Add issue to Firestore
        issue_ref = self.db.collection('issues').document()
        issue_ref.set(issue_data)
        issue_id = issue_ref.id
        
        print(f"Created sample issue with ID: {issue_id}")
        
        # Process the issue
        result = self.process_new_issue(issue_id)
        if result:
            print("Issue processed successfully!")
        else:
            print("Failed to process issue.")

def main():
    # Initialize the ward notification system
    system = WardNotificationSystem()
    
    # FIXED: Check if email credentials are properly set
    if not system.email_sender or not system.email_password:
        print("ERROR: Email credentials not set. Please check your .env file.")
        print(f"Found email_sender: {system.email_sender}")
        print(f"Email password exists: {'Yes' if system.email_password else 'No'}")
        return
    
    # Setup the wards collection if it doesn't exist
    system.setup_ward_collection()
    
    # Explain how to set up the trigger
    system.setup_firestore_trigger()
    
    # For testing, process a sample issue
    system.test_with_sample_issue()
    
    print("Ward notification system is ready!")

if __name__ == "__main__":
    main()
