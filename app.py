# app.py
from flask import Flask, request, jsonify, Response
import torch.nn.functional as F
import make_maps
import os
import numpy as np
from PIL import Image, UnidentifiedImageError
import io
import torch
import torchvision.transforms as transforms
from torchvision.models import resnet50, ResNet50_Weights
from transformers import BertTokenizer, BertModel
from sklearn.metrics.pairwise import cosine_similarity
import math
from datetime import datetime
import uuid
import base64
import firebase_admin
from firebase_admin import credentials, firestore

# Add an admin key for authentication
ADMIN_KEY = os.getenv('ADMIN_KEY', 'default_admin_key')  # Replace 'default_admin_key' with a secure key

app = Flask(__name__)

# Initialize Firebase
def initialize_firebase():
    # You need to download your Firebase service account key from Firebase console
    # and save it as 'serviceAccountKey.json' in your project directory
    # or set the path to your Firebase credentials file
    cred = credentials.Certificate('serviceAccountKey.json')
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    return db

# Initialize models
def initialize_models():
    # Image classification model (ResNet50)
    image_model = resnet50(weights=ResNet50_Weights.IMAGENET1K_V2)
    image_model.eval()
    
    # Text classification model (BERT)
    text_tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')
    text_model = BertModel.from_pretrained('bert-base-uncased')
    text_model.eval()
    
    return {
        'image_model': image_model,
        'text_model': text_model,
        'text_tokenizer': text_tokenizer
    }

# Category mapping
CATEGORIES = {
    0: "pothole",
    1: "garbage",
    2: "streetlight",
    3: "graffiti",
    4: "flooding",
    5: "sidewalk_damage"
}

# Simplified category classes for image classification
IMAGE_CLASSES = {
    'pothole': [609, 721, 767],  # Relevant ImageNet classes that might indicate potholes
    'garbage': [768, 772, 910],  # Classes for garbage/trash
    'streetlight': [825, 654, 846],  # Classes for streetlights
    'graffiti': [890, 879, 747],  # Classes that might indicate painted surfaces
    'flooding': [978, 979, 756],  # Classes for water
    'sidewalk_damage': [724, 517, 609]  # Classes for damage
}

# Haversine formula to calculate distance between two GPS coordinates
def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371000  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(delta_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c  # Distance in meters

def process_image(image_data, models):
    # Convert base64 to image
    print(image_data)
    image_bytes = base64.b64decode(image_data)
    image = Image.open(io.BytesIO(image_bytes)).convert('RGB')
    
    # Preprocess image for ResNet
    preprocess = transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])
    
    image_tensor = preprocess(image).unsqueeze(0)
    
    # Get features
    with torch.no_grad():
        features = models['image_model'](image_tensor)
        
    # Get predicted class
    probs = torch.nn.functional.softmax(features[0], dim=0)
    top5_probs, top5_indices = torch.topk(probs, 5)
    top5_classes = top5_indices.tolist()
    
    # Convert features to embedding
    embedding = features.flatten().numpy()
    
    # Determine category based on ImageNet class
    category = []
    # for cat, class_ids in IMAGE_CLASSES.items():
    #     if predicted_class in class_ids:
    #         category.append(cat)
    #         break
    
    # Default to most likely if no match
    categories_list = list(CATEGORIES.values())

    for class_idx in top5_classes:
        mapped_category = categories_list[class_idx % len(categories_list)]
        if mapped_category not in category:
            category.append(mapped_category)
    
    return {
        'embedding': embedding,
        'category': category #list of possible categories
    
    }

# Process image and encode it to base64
def process_image_for_storage(image_data):
    try:
        # Attempt to decode the base64 string into image bytes
        image_bytes = base64.b64decode(image_data)

        # Attempt to open the image using PIL
        image = Image.open(io.BytesIO(image_bytes))

        # Check if the image is valid and convert to RGB if needed
        image = image.convert('RGB')

        # Save the image to a BytesIO buffer as JPEG format
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG")  # Save as JPEG regardless of original format
        image_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

        return image_base64
    
    except (base64.binascii.Error, UnidentifiedImageError) as e:
        # If base64 decoding or image opening fails, handle the error
        print(f"Error processing image: {e}")
        return None  # You can return an error message or a default image base64 instead

# Process text and extract features
def process_text(text, models):
    tokenizer = models['text_tokenizer']
    model = models['text_model']
    
    # Preprocess text
    inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=128)
    
    # Get features
    with torch.no_grad():
        outputs = model(**inputs)
        
    # Get CLS token embedding as text representation
    embedding = outputs.last_hidden_state[:, 0, :].numpy().flatten()
    
    # Simple keyword-based category detection
    category_keywords = {
        'pothole': ['pothole', 'hole', 'crater', 'road damage'],
        'garbage': ['garbage', 'trash', 'waste', 'litter', 'dump'],
        'streetlight': ['streetlight', 'light', 'lamp', 'lighting', 'pole'],
        'graffiti': ['graffiti', 'paint', 'vandalism', 'drawing', 'spray'],
        'flooding': ['flood', 'water', 'puddle', 'drain', 'clogged'],
        'sidewalk_damage': ['sidewalk', 'pavement', 'crack', 'broken', 'uneven']
    }
    
    # Default category and confidence
    category = 'unknown'
    max_count = 0
    
    # Simple keyword matching
    text_lower = text.lower()
    for cat, keywords in category_keywords.items():
        count = sum(1 for keyword in keywords if keyword in text_lower)
        if count > max_count:
            max_count = count
            category = cat
    
    return {
        'embedding': embedding,
        'category': category
    }

#  Modify the store_issue function to compare image and text categories
def store_issue(issue_data, image_embedding, text_embedding, image_category, text_category, image_base64):
    db = app.config['db']
    
    issue_id = str(uuid.uuid4())
    created_at = datetime.now().isoformat()
    
    # Convert numpy arrays to base64 strings for storage
    image_embedding_base64 = base64.b64encode(image_embedding.tobytes()).decode('utf-8')
    text_embedding_base64 = base64.b64encode(text_embedding.tobytes()).decode('utf-8')
    
    # Determine final category - use detected categories if they match, otherwise use user input
    final_category = issue_data['category']
    if image_category == text_category:
        final_category = image_category
    
    # Check for similar issues to increment counter
    nearby_issues = find_nearby_issues(issue_data['latitude'], issue_data['longitude'], radius=50)  # Smaller radius for exact location
    similar_issues = []
    
    for issue in nearby_issues:
        # Get issue embedding
        issue_image_embedding, _ = get_issue_embedding(issue['issue_id'])
        
        if issue_image_embedding is not None:
            # Reshape for cosine similarity
            embedding1 = image_embedding.reshape(1, -1)
            embedding2 = issue_image_embedding.reshape(1, -1)
            
            # Calculate similarity
            similarity = cosine_similarity(embedding1, embedding2)[0][0]
            
            # Check if similar (threshold = 0.8)
            if similarity > 0.8 and issue['category'] == final_category:
                similar_issues.append(issue)
    
    # Count of similar issues
    similar_count = len(similar_issues)
    
    # Create the issue document
    issue_ref = db.collection('issues').document(issue_id)
    issue_ref.set({
        'latitude': issue_data['latitude'],
        'longitude': issue_data['longitude'],
        'category': final_category,
        'description': issue_data.get('description', ''),
        'status': 'open',
        'created_at': created_at,
        'image_embedding': image_base64,
        'text_embedding': text_embedding_base64,
        'similar_count': similar_count,  # Adding the counter for similar issues
        'image_category': image_category,  # Store original detected categories for reference
        'text_category': text_category
    })
    
    # Update similar issues' counters
    for similar in similar_issues:
        similar_ref = db.collection('issues').document(similar['issue_id'])
        # Use a transaction to safely increment the counter
        transaction = db.transaction()
        
        @firestore.transactional
        def update_in_transaction(transaction, issue_ref):
            issue_doc = issue_ref.get(transaction=transaction)
            if issue_doc.exists:
                current_count = issue_doc.get('similar_count') or 0
                transaction.update(issue_ref, {
                    'similar_count': current_count + 1
                })
        
        update_in_transaction(transaction, similar_ref)
    
    return issue_id


# Find nearby issues using Firestore
def find_nearby_issues(latitude, longitude, radius=100):
    db = app.config['db']
    
    # Get all issues (Firestore doesn't support geospatial queries natively for this distance calculation)
    # For a production app, consider using GeoFirestore or other specialized solutions
    issues_ref = db.collection('issues')
    issues = issues_ref.stream()
    
    nearby_issues = []
    for issue in issues:
        issue_data = issue.to_dict()
        issue_id = issue.id
        
        issue_lat = issue_data.get('latitude')
        issue_lon = issue_data.get('longitude')
        
        if issue_lat is None or issue_lon is None:
            continue
        
        # Calculate distance
        distance = haversine_distance(latitude, longitude, issue_lat, issue_lon)
        
        # Check if within radius
        if distance <= radius:
            nearby_issues.append({
                'issue_id': issue_id,
                'location': {'lat': issue_lat, 'lon': issue_lon},
                'category': issue_data.get('category'),
                'description': issue_data.get('description'),
                'status': issue_data.get('status'),
                'distance': distance
            })
    
    return nearby_issues

# Get issue embedding from Firebase
def get_issue_embedding(issue_id):
    db = app.config['db']
    
    issue_ref = db.collection('issues').document(issue_id)
    issue = issue_ref.get()
    
    if issue.exists:
        issue_data = issue.to_dict()
        
        image_embedding_base64 = issue_data.get('image_embedding')
        text_embedding_base64 = issue_data.get('text_embedding')
        if not image_embedding_base64.startswith(("/9j", "iVBORw0KGgo")):
            return None, None
        
        if image_embedding_base64 and text_embedding_base64:
            image_embedding_bytes = base64.b64decode(image_embedding_base64)
            image_embedding = np.frombuffer(image_embedding_bytes, dtype=np.float32)
            
            text_embedding_bytes = base64.b64decode(text_embedding_base64)
            text_embedding = np.frombuffer(text_embedding_bytes, dtype=np.float32)
            print("store_issue") 
            return process_image(image_embedding_base64, app.config['models'])['embedding'], text_embedding
    
    return None, None

# Check for duplicate issues
@app.route('/check-duplicate', methods=['POST'])
def check_duplicate():
    data = request.json
    
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    image_data = data.get('image')
    category = data.get('category')
    
    # Find nearby issues
    nearby_issues = find_nearby_issues(latitude, longitude)
    
    # No nearby issues
    if not nearby_issues:
        return jsonify({
            'duplicate_found': False,
            'similar_issues': []
        })
    
    # Process current image
    models = app.config['models']
    image_result = process_image(image_data, models)
    # text_result = process_text
    current_embedding = image_result['embedding']
    
    # Compare with nearby issues
    similar_issues = []
    for issue in nearby_issues:
        # Get issue embedding
        issue_image_embedding, _ = get_issue_embedding(issue['issue_id'])
        
        if issue_image_embedding is not None:
            # Reshape for cosine similarity
            embedding1 = current_embedding.reshape(1, -1)
            embedding2 = issue_image_embedding.reshape(1, -1)
            
            # Calculate similarity
            similarity = cosine_similarity(embedding1, embedding2)[0][0]
            
            # Check if similar (threshold = 0.8)
            if similarity > 0.8 and issue['category'] == category:
                issue['similarity'] = float(similarity)
                similar_issues.append(issue)
    
    return jsonify({
        'duplicate_found': len(similar_issues) > 0,
        'similar_issues': similar_issues
    })

@app.route('/validate-description', methods=['POST'])
def validate_description():
    try:
        data = request.json
        
        if not data:
            return jsonify({
                'error': 'No JSON data provided'
            }), 400
        
        image_data = data.get('image')
        description = data.get('description')
        
        if not image_data:
            return jsonify({
                'error': 'No image data provided'
            }), 400
            
        if not description:
            return jsonify({
                'error': 'No description provided'
            }), 400
        
        models = app.config['models']
        
        # Process image
        image_result = process_image(image_data, models)
        image_category = image_result['category']
        
        # Process text
        text_result = process_text(description, models)
        text_category = text_result['category']
        
        # We can't directly compare embeddings with different dimensions
        # So instead of similarity, we'll check if categories match
        match = text_category in image_category
        
        # Use a simplified confidence score based on category match
        confidence_score = 0.9 if match else 0.3
        
        suggestion = "Valid report" if match else f"Mismatch detected: Image shows '{image_category[0]}' but description indicates '{text_category}'"
        
        return jsonify({
            'match': match,
            'image_category': text_category if text_category in image_category else image_category[0],
            'description_category': text_category,
            'confidence_score': confidence_score,
            'suggestion': suggestion
        })
    except Exception as e:
        # Log the error - in production you'd use a proper logger
        print(f"Error in validate_description: {str(e)}")
        # Return a friendly error message
        return jsonify({
            'error': 'An error occurred while processing the request',
            'message': str(e)
        }), 500

# Modify the report_issue endpoint to pass the detected categories
@app.route('/report-issue', methods=['POST'])
def report_issue():
    data = request.json
    
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    category = data.get('category')
    description = data.get('description', '')
    image_data = data.get('image')
    
    models = app.config['models']
    
    # Process image and text
    image_result = process_image(image_data, models)
    text_result = process_text(description, models)
    
    image_category = image_result['category']
    text_category = text_result['category']
    
    # Auto-validate
    if text_category not in image_category:
        return jsonify({
            'success': False,
            'message': f"Mismatch detected: Image shows '{image_category}' but description indicates '{text_category}'. Issue not reported."
        }), 400
    
    image_base64 = process_image_for_storage(image_data)
    # If valid, store the issue
    issue_id = store_issue(
        {'latitude': latitude, 'longitude': longitude, 'category': category, 'description': description},
        image_result['embedding'],
        text_result['embedding'],
        text_category,
        text_category,
        image_base64
    )
    
    return jsonify({
        'success': True,
        'issue_id': issue_id,
        'message': 'Issue reported successfully'
    })


# Get nearby issues
@app.route('/issues-nearby', methods=['GET'])
def issues_nearby():
    latitude = float(request.args.get('latitude'))
    longitude = float(request.args.get('longitude'))
    radius = float(request.args.get('radius', 500))  # Default 500m
    
    nearby_issues = find_nearby_issues(latitude, longitude, radius)
    
    return jsonify({
        'issues': nearby_issues
    })

# Get issue details
# Update get_issue to include similar_count
@app.route('/issue/<issue_id>', methods=['GET'])
def get_issue(issue_id):
    db = app.config['db']
    
    issue_ref = db.collection('issues').document(issue_id)
    issue = issue_ref.get()
    
    if not issue.exists:
        return jsonify({
            'success': False,
            'message': 'Issue not found'
        }), 404
    
    issue_data = issue.to_dict()
    
    return jsonify({
        'success': True,
        'issue': {
            'id': issue_id,
            'location': {'lat': issue_data.get('latitude'), 'lon': issue_data.get('longitude')},
            'category': issue_data.get('category'),
            'description': issue_data.get('description'),
            'status': issue_data.get('status'),
            'created_at': issue_data.get('created_at'),
            'similar_count': issue_data.get('similar_count', 0),  # Include the similar count
            'image_category': issue_data.get('image_category'),  # Include detected categories
            'text_category': issue_data.get('text_category')
        }
    })

# Add a new endpoint to get similar issues counts by location
@app.route('/similar-issues-count', methods=['GET'])
def similar_issues_count():
    latitude = float(request.args.get('latitude'))
    longitude = float(request.args.get('longitude'))
    radius = float(request.args.get('radius', 500))  # Default 500m
    
    nearby_issues = find_nearby_issues(latitude, longitude, radius)
    
    # Group by category and count
    category_counts = {}
    for issue in nearby_issues:
        category = issue.get('category')
        if category not in category_counts:
            category_counts[category] = 0
        category_counts[category] += 1
    
    # Calculate highest similar count
    highest_similar_count = 0
    for issue in nearby_issues:
        similar_count = issue.get('similar_count', 0)
        if similar_count > highest_similar_count:
            highest_similar_count = similar_count
    
    return jsonify({
        'category_counts': category_counts,
        'highest_similar_count': highest_similar_count,
        'total_issues': len(nearby_issues)
    })

# Vote on an issue
@app.route('/vote/<issue_id>', methods=['POST'])
def vote_issue(issue_id):
    # In a real app, you would store votes in a separate collection
    db = app.config['db']
    
    # Create a unique ID for the vote using the issue_id and a random UUID
    vote_id = f"{issue_id}_{str(uuid.uuid4())}"
    
    # Store the vote in a votes collection
    vote_ref = db.collection('votes').document(vote_id)
    vote_ref.set({
        'issue_id': issue_id,
        'created_at': datetime.now().isoformat(),
        # You might want to add user ID or other metadata here
    })
    
    # Count total votes for this issue
    votes = db.collection('votes').where('issue_id', '==', issue_id).stream()
    vote_count = sum(1 for _ in votes)
    
    return jsonify({
        'success': True,
        'message': f'Vote recorded for issue {issue_id}',
        'vote_count': vote_count
    })

# Update issue status (admin only)
@app.route('/resolve/<issue_id>', methods=['POST'])
def resolve_issue(issue_id):
    data = request.json
    admin_key = data.get('admin_key')  # Expect admin_key in the request body

    # Check if the admin key is valid
    if admin_key != ADMIN_KEY:
        return jsonify({
            'success': False,
            'message': 'Unauthorized: Invalid admin key'
        }), 403

    new_status = data.get('status', 'resolved')
    
    db = app.config['db']
    issue_ref = db.collection('issues').document(issue_id)
    issue = issue_ref.get()
    
    if not issue.exists:
        return jsonify({
            'success': False,
            'message': 'Issue not found'
        }), 404
    
    # Update the status
    issue_ref.update({
        'status': new_status,
        'resolved_at': datetime.now().isoformat()
    })

    return jsonify({
        'success': True,
        'message': f'Issue {issue_id} status updated to {new_status}'
    })


# Add these debugging endpoints
@app.route('/health', methods=['GET'])
def health_check():
    """Simple endpoint to check if the API is running."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/models-check', methods=['GET'])
def models_check():
    """Check if all models are loaded properly."""
    try:
        models = app.config.get('models', {})
        
        return jsonify({
            'status': 'ok',
            'models_loaded': bool(models),
            'available_models': list(models.keys()) if models else []
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# Test endpoint for image processing
@app.route('/test-image', methods=['POST'])
def test_image():
    """Test image processing."""
    try:
        data = request.json
        image_data = data.get('image')
        
        if not image_data:
            return jsonify({'error': 'No image data provided'}), 400
            
        models = app.config['models']
        result = process_image(image_data, models)
        
        return jsonify({
            'category': result['category'],
            'embedding_shape': result['embedding'].shape,
            'embedding_type': str(result['embedding'].dtype)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Test endpoint for text processing  
@app.route('/test-text', methods=['POST'])
def test_text():
    """Test text processing."""
    try:
        data = request.json
        text = data.get('text')
        
        if not text:
            return jsonify({'error': 'No text provided'}), 400
            
        models = app.config['models']
        result = process_text(text, models)
        
        return jsonify({
            'category': result['category'],
            'embedding_shape': result['embedding'].shape,
            'embedding_type': str(result['embedding'].dtype)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Firebase database test endpoint
@app.route('/firebase-test', methods=['GET'])
def firebase_test():
    """Test if Firebase connection is working."""
    try:
        db = app.config['db']
        
        # Try to read from a test collection
        test_ref = db.collection('test').document('test')
        test_ref.set({
            'test': True,
            'timestamp': datetime.now().isoformat()
        })
        
        test_doc = test_ref.get()
        
        return jsonify({
            'status': 'ok',
            'connected': test_doc.exists,
            'message': 'Firebase connection successful'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# Initialize the Flask app
def initialize_app(app):
    # Initialize Firebase
    db = initialize_firebase()
    app.config['db'] = db
    
    # Load models
    app.config['models'] = initialize_models()
    
    return app

@app.route('/map/<category_name>')
def show_map(category_name):
    db = app.config['db']  # Firebase DB initialized somewhere before running
    map_html = make_maps.generate_category_map(db, category_name)

    if map_html is None:
        return f"No data found for category: {category_name}", 404

    return Response(map_html, mimetype='text/html')

# Initialize the app
app = initialize_app(app)

if __name__ == '__main__':
    app.run(debug=True)
