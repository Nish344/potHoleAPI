# firebase_test_client.py
import requests
import base64
import json
import time
import os
import argparse
from PIL import Image
import io
import numpy as np
from tabulate import tabulate
from datetime import datetime

# API base URL
BASE_URL = 'http://localhost:5000'

# Admin key for authentication - should match the value in app.py
ADMIN_KEY = os.getenv('ADMIN_KEY', 'default_admin_key')

# Helper function to load and encode an image
def load_image(image_path):
    with open(image_path, 'rb') as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

# Sample test data - in a real app these would be real images
sample_images = {
    'pothole1': 'sample_images/pothole1.jpg',
    'pothole2': 'sample_images/pothole2.jpg',  # Similar to pothole1 but slightly different angle
    'garbage': 'sample_images/garbage.jpg',
    'streetlight': 'sample_images/streetlight.jpg',
    'graffiti': 'sample_images/graffiti.jpg',
    'flooding': 'sample_images/flooding.jpg',
    'sidewalk': 'sample_images/sidewalk.jpg',
}

# Create sample_images directory if it doesn't exist
os.makedirs('sample_images', exist_ok=True)

# Function to check if image exists and create a placeholder if not
def ensure_sample_images():
    for img_name, img_path in sample_images.items():
        if not os.path.exists(img_path):
            print(f"Creating placeholder image for {img_name} at {img_path}")
            # Create a simple colored image as placeholder
            img = Image.new('RGB', (500, 500), color=(
                hash(img_name) % 256,
                (hash(img_name) // 256) % 256,
                (hash(img_name) // 65536) % 256
            ))
            img.save(img_path)

# Test Firebase Connection
def test_firebase_connection():
    print("\n=== Testing Firebase Connection ===")
    try:
        response = requests.get(f'{BASE_URL}/firebase-test')
        print(f"Status Code: {response.status_code}")
        result = response.json()
        print(f"Response: {json.dumps(result, indent=2)}")
        
        if result.get('status') == 'ok' and result.get('connected'):
            print("✅ Firebase connection successful!")
            return True
        else:
            print("❌ Firebase connection failed!")
            return False
    except Exception as e:
        print(f"❌ Error testing Firebase connection: {str(e)}")
        return False

# Test 1: Report a new issue
def report_issue(lat=37.7749, lon=-122.4194, category='pothole', description='Test issue', image_key='pothole1'):
    print("\n=== Reporting a new issue ===")
    
    # Load sample image
    image_data = load_image(sample_images[image_key])
    
    # Create report data
    report_data = {
        'latitude': lat,
        'longitude': lon,
        'category': category,
        'description': description,
        'image': image_data
    }
    
    # Send request
    response = requests.post(f'{BASE_URL}/report-issue', json=report_data)
    result = response.json()
    
    print(f"Response: {json.dumps(result, indent=2)}")
    
    # Return issue ID for next tests
    return result.get('issue_id')

# Check for duplicate issues
def check_duplicate(lat=37.7749, lon=-122.4194, category='pothole', image_key='pothole1'):
    print("\n=== Checking for duplicate issues ===")
    
    image_data = load_image(sample_images[image_key])
    
    check_data = {
        'latitude': lat,
        'longitude': lon,
        'category': category,
        'image': image_data
    }
    
    # Send request
    response = requests.post(f'{BASE_URL}/check-duplicate', json=check_data)
    result = response.json()
    
    print(f"Response: {json.dumps(result, indent=2)}")
    return result

# Validate description
def validate_description(description, image_key='pothole1'):
    print("\n=== Validating image and description consistency ===")
    
    try:
        # Load image
        image_data = load_image(sample_images[image_key])
        
        # Create validation data
        validation_data = {
            'image': image_data,
            'description': description
        }
        
        # Send request
        response = requests.post(f'{BASE_URL}/validate-description', json=validation_data)
        
        # Print status code for debugging
        print(f"Status Code: {response.status_code}")
        
        if response.content:
            try:
                result = response.json()
                print(f"Response: {json.dumps(result, indent=2)}")
                return result
            except json.JSONDecodeError:
                print(f"Error: Invalid JSON response: {response.text[:100]}...")
                return None
        else:
            print("Error: Empty response from server")
            return None
            
    except Exception as e:
        print(f"Error during test: {str(e)}")
        return None

# Get nearby issues
def get_nearby_issues(lat=37.7749, lon=-122.4194, radius=1000):
    print("\n=== Getting nearby issues ===")
    
    # Query parameters
    params = {
        'latitude': lat,
        'longitude': lon,
        'radius': radius  # 1000 meters radius
    }
    
    # Send request
    response = requests.get(f'{BASE_URL}/issues-nearby', params=params)
    result = response.json()
    
    print(f"Found {len(result.get('issues', []))} issues nearby")
    
    # Format issues as a table
    if 'issues' in result and result['issues']:
        issues_table = []
        for issue in result['issues']:
            issues_table.append([
                issue.get('issue_id', '')[:8] + '...',
                issue.get('category', ''),
                issue.get('status', ''),
                f"{issue.get('distance', 0):.1f}m",
                issue.get('similar_count', 0)  # Add similar count to table
            ])
        print("\nNearby Issues:")
        print(tabulate(issues_table, headers=['ID', 'Category', 'Status', 'Distance', 'Similar Count']))
    
    return result.get('issues', [])

# Get issue details
def get_issue_details(issue_id):
    print(f"\n=== Getting details for issue {issue_id} ===")
    
    # Send request
    response = requests.get(f'{BASE_URL}/issue/{issue_id}')
    result = response.json()
    
    print(f"Response: {json.dumps(result, indent=2)}")
    
    # Display detected categories vs. final category
    if 'issue' in result and result['success']:
        issue = result['issue']
        print("\nCategory Information:")
        print(f"Final Category: {issue.get('category')}")
        print(f"Image-Detected Category: {issue.get('image_category')}")
        print(f"Text-Detected Category: {issue.get('text_category')}")
        print(f"Similar Issues Count: {issue.get('similar_count', 0)}")
    
    return result

# Vote on an issue
def vote_on_issue(issue_id):
    print(f"\n=== Voting for issue {issue_id} ===")
    
    # Send request
    response = requests.post(f'{BASE_URL}/vote/{issue_id}', json={'vote': 'up'})
    result = response.json()
    
    print(f"Response: {json.dumps(result, indent=2)}")
    return result

# Change issue status (open/resolved)
def change_issue_status(issue_id, status='resolved'):
    print(f"\n=== Changing issue {issue_id} status to {status} ===")

    # Send request with admin key
    response = requests.post(f'{BASE_URL}/resolve/{issue_id}', json={
        'status': status,
        'admin_key': ADMIN_KEY
    })
    result = response.json()

    print(f"Response: {json.dumps(result, indent=2)}")
    return result

# List all issues (internal function that gets issues nearby with a large radius)
def list_all_issues():
    print("\n=== Listing all issues ===")
    issues = get_nearby_issues(radius=100000)  # Very large radius to get all issues
    return issues

# Get similar issues count by location
def get_similar_issues_count(lat=37.7749, lon=-122.4194, radius=1000):
    print(f"\n=== Getting similar issues count within {radius}m ===")
    
    # Query parameters
    params = {
        'latitude': lat,
        'longitude': lon,
        'radius': radius
    }
    
    # Send request
    response = requests.get(f'{BASE_URL}/similar-issues-count', params=params)
    result = response.json()
    
    print(f"Response: {json.dumps(result, indent=2)}")
    
    # Format category counts as a table
    if 'category_counts' in result and result['category_counts']:
        cat_table = []
        for category, count in result['category_counts'].items():
            cat_table.append([category, count])
        print("\nCategory Counts:")
        print(tabulate(cat_table, headers=['Category', 'Count']))
    
    return result

# Interactive menu for issue management
def interactive_menu():
    print("\n" + "="*50)
    print("CivicChain Firebase Issue Management")
    print("="*50)
    
    while True:
        print("\nOptions:")
        print("1. Report a new issue")
        print("2. List all issues")
        print("3. Check for duplicate issues")
        print("4. Validate description")
        print("5. Get issue details")
        print("6. Vote on an issue")
        print("7. Change issue status (open/resolved)")
        print("8. Test Firebase connection")
        print("9. Run automated tests")
        print("10. Display Maps")
        print("11. Get similar issues count")  # New option
        print("0. Exit")
        
        choice = input("\nEnter your choice: ")
        
        if choice == "1":
            # Get issue details from user
            category = input("Enter category (pothole, garbage, streetlight, graffiti, flooding, sidewalk_damage): ")
            description = input("Enter description: ")
            
            # Use default lat/lon if not specified
            lat = float(input("Enter latitude (default 37.7749): ") or "37.7749")
            lon = float(input("Enter longitude (default -122.4194): ") or "-122.4194")
            
            # Select image
            print("\nAvailable test images:")
            for i, img in enumerate(sample_images.keys()):
                print(f"{i+1}. {img}")
            img_choice = int(input("Select image number: ")) - 1
            image_key = list(sample_images.keys())[img_choice]
            
            # Report the issue
            issue_id = report_issue(lat, lon, category, description, image_key)
            print(f"\nIssue reported with ID: {issue_id}")
            
        elif choice == "2":
            # List all issues
            issues = list_all_issues()
            
        elif choice == "3":
            # Get parameters for duplicate check
            lat = float(input("Enter latitude (default 37.7749): ") or "37.7749")
            lon = float(input("Enter longitude (default -122.4194): ") or "-122.4194")
            category = input("Enter category (default pothole): ") or "pothole"
            
            # Select image
            print("\nAvailable test images:")
            for i, img in enumerate(sample_images.keys()):
                print(f"{i+1}. {img}")
            img_choice = int(input("Select image number: ")) - 1
            image_key = list(sample_images.keys())[img_choice]
            
            # Check for duplicates
            check_duplicate(lat, lon, category, image_key)
            
        elif choice == "4":
            # Get parameters for validation
            description = input("Enter description to validate: ")
            
            # Select image
            print("\nAvailable test images:")
            for i, img in enumerate(sample_images.keys()):
                print(f"{i+1}. {img}")
            img_choice = int(input("Select image number: ")) - 1
            image_key = list(sample_images.keys())[img_choice]
            
            # Validate
            validate_description(description, image_key)
            
        elif choice == "5":
            # Get issue ID
            issue_id = input("Enter issue ID: ")
            get_issue_details(issue_id)
            
        elif choice == "6":
            # Get issue ID
            issue_id = input("Enter issue ID: ")
            vote_on_issue(issue_id)
            
        elif choice == "7":
            # Get issue ID and new status
            issue_id = input("Enter issue ID: ")
            status = input("Enter new status (open/resolved): ")
            change_issue_status(issue_id, status)
            
        elif choice == "8":
            # Test Firebase connection
            test_firebase_connection()
            
        elif choice == "9":
            # Run automated tests
            run_automated_tests()
            
        elif choice == "10":
            test_maps()
            
        elif choice == "11":
            # Get similar issues count
            lat = float(input("Enter latitude (default 37.7749): ") or "37.7749")
            lon = float(input("Enter longitude (default -122.4194): ") or "-122.4194")
            radius = float(input("Enter radius in meters (default 1000): ") or "1000")
            get_similar_issues_count(lat, lon, radius)
            
        elif choice == "0":
            print("Goodbye!")
            break
        else:
            print("Invalid choice, please try again.")

# Run automated tests
def run_automated_tests():
    print("\n=== Running Automated Tests ===")
    
    # Test health and models
    test_health()
    test_models_check()
    
    # Test Firebase connection
    if not test_firebase_connection():
        print("❌ Skipping further tests due to Firebase connection failure")
        return
    
    # Create an issue with matching image and text categories
    issue_id1 = report_issue(
        lat=37.7749, 
        lon=-122.4194, 
        category='pothole', 
        description='Automated test issue - deep pothole on main road',
        image_key='pothole1'
    )
    
    # Wait for Firebase operations to complete
    time.sleep(2)
    
    # Create another similar issue at the same location (should increment counter)
    issue_id2 = report_issue(
        lat=37.7750,  # Slightly different location but within 50m radius
        lon=-122.4195, 
        category='pothole', 
        description='Another pothole in the same area',
        image_key='pothole2'  
    )
    
    # Wait for Firebase operations to complete
    time.sleep(2)
    
    # Create an issue with non-matching image and text categories
    issue_id3 = report_issue(
        lat=37.7755,  # Different location
        lon=-122.4200, 
        category='streetlight', 
        description='The garbage bin is overflowing',  # Text suggests garbage but image is streetlight
        image_key='streetlight'
    )
    
    # Wait for Firebase operations to complete
    time.sleep(2)
    
    # Get nearby issues including our new ones
    nearby_issues = get_nearby_issues(lat=37.7749, lon=-122.4194, radius=500)
    
    # Check for duplicate
    check_duplicate(lat=37.7749, lon=-122.4194, category='pothole', image_key='pothole1')
    
    # Test validation - should match
    validate_description('There is a pothole in the middle of the road', 'pothole1')
    
    # Test validation - should NOT match
    validate_description('The streetlight is broken and not working', 'pothole1')
    
    # Test getting issue details with final category and counter
    if issue_id1:
        print("\n=== Testing issue with matching image and text categories ===")
        get_issue_details(issue_id1)
    
    if issue_id3:
        print("\n=== Testing issue with non-matching image and text categories ===")
        get_issue_details(issue_id3)
    
    # Test getting similar issues count
    get_similar_issues_count(lat=37.7749, lon=-122.4194, radius=500)
    
    # Test voting and resolving on the first issue
    if issue_id1:
        vote_on_issue(issue_id1)
        change_issue_status(issue_id1, 'resolved')
        change_issue_status(issue_id1, 'open')
    
    print("\n✅ Automated tests completed!")

# Test API Health
def test_health():
    print("\n=== Testing API Health ===")
    try:
        response = requests.get(f'{BASE_URL}/health')
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {str(e)}")
        return False

# Test maps feat
def test_maps():
    cat_dict = {
        "1": "pothole",
        "2": "garbage",
        "3": "streetlight",
        "4": "graffiti",
        "5": "flooding",
        "6": "sidewalk_damage",
        "7": "go back"
    }
    while True:
        category = input('''
Enter one category number
1.pothole
2.garbage
3.streetlight
4.graffiti
5.flooding
6.sidewalk_damage
7.exit
    ''')
        if(category == "7"):
           break
        try:
            if(int(category) > 7 or int(category) < 0):
                break
        except ValueError:
            print("Not a valid choice")
            break
        print(f"{BASE_URL}/map/{cat_dict.get(category, '')}")

# Test Models Check
def test_models_check():
    print("\n=== Testing Models Loading ===")
    try:
        response = requests.get(f'{BASE_URL}/models-check')
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {str(e)}")
        return False

if __name__ == '__main__':
    print("CivicChain Firebase Test Client")
    print("Make sure the Flask server is running!")
    
    # Check if sample images exist and create placeholders if needed
    ensure_sample_images()
    
    parser = argparse.ArgumentParser(description='Test CivicChain Firebase API')
    parser.add_argument('--automated', action='store_true', help='Run automated tests')
    parser.add_argument('--report', action='store_true', help='Report a test issue')
    parser.add_argument('--list', action='store_true', help='List all issues')
    parser.add_argument('--resolve', metavar='ISSUE_ID', help='Resolve an issue by ID')
    parser.add_argument('--open', metavar='ISSUE_ID', help='Reopen an issue by ID')
    parser.add_argument('--details', metavar='ISSUE_ID', help='Get issue details by ID')
    parser.add_argument('--similar', action='store_true', help='Get similar issues count')
    parser.add_argument('--interactive', action='store_true', help='Run interactive menu')
    
    args = parser.parse_args()
    
    try:
        if args.automated:
            run_automated_tests()
        elif args.report:
            issue_id = report_issue()
            print(f"Issue reported with ID: {issue_id}")
        elif args.list:
            list_all_issues()
        elif args.resolve:
            change_issue_status(args.resolve, 'resolved')
        elif args.open:
            change_issue_status(args.open, 'open')
        elif args.details:
            get_issue_details(args.details)
        elif args.similar:
            get_similar_issues_count()
        elif args.interactive or not any(vars(args).values()):
            # If no arguments or --interactive, run the interactive menu
            interactive_menu()
    except requests.exceptions.ConnectionError:
        print("\nError: Could not connect to the API server.")
        print(f"Make sure the Flask server is running on {BASE_URL}")
    except Exception as e:
        print(f"\nError: {str(e)}")
