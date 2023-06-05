import os
import io
import tensorflow
from tensorflow import keras
import numpy as np
from PIL import Image
from flask import Flask, request, jsonify
import requests
from google.oauth2 import service_account
from google.cloud import firestore, storage
import firebase_admin
from firebase_admin import auth, credentials
from uuid import uuid4
from functools import wraps

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'config/service-account.json'

cred = credentials.Certificate('config/service-account.json')
firebase_admin.initialize_app(cred)


model = keras.models.load_model("model.h5")
label = ['Pohon Beringin','Pohon Bungur','Pohon Cassia','Pohon Jati','Pohon Kenanga','Pohon Kerai Payung','Pohon Saga','Pohon Trembesi','pohon Mahoni','pohon Matoa']

app = Flask(__name__)

#declaration using firestore and storage bucket
db = firestore.Client(project='jejak-karbon-bangkit23')
storage_client = storage.Client(project='jejak-karbon-bangkit23')

#definition working of ML
def predict_label(img):
    i = np.asarray(img) / 255.0
    i = i.reshape(1, 224, 224, 3)
    pred = model.predict(i)
    result = label[np.argmax(pred)]
    return result

# Middleware for authorization checking
def validate_token(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        authorization = request.headers.get('Authorization')
        if not authorization or not authorization.startswith('Bearer '):
            return jsonify({'error': 'Unauthorized'}), 403

        token = authorization.split('Bearer ')[1]

        try:
            decoded_token = firebase_admin.auth.verify_id_token(token)
            request.user_id = decoded_token['uid']
            request.email = decoded_token['email']
            # Get the user object to retrieve the username
            user = firebase_admin.auth.get_user(decoded_token['uid'])
            request.username = user.display_name
        except firebase_admin.auth.InvalidIdTokenError:
            return jsonify({'error': 'Unauthorized'}), 402
        

        return f(*args, **kwargs)
    return decorated_function


   
@app.route("/predict", methods=["POST"])
@validate_token
def predict():
    file = request.files.get('file')
    

    # Check if file is None or filename is empty
    if file is None or file.filename == "":
        return jsonify({"error": "No file provided"}), 400
    
    # Upload the file to Google Cloud Storage
    bucket = storage_client.bucket('img-plant')
    blob = bucket.blob(file.filename)
    blob.upload_from_file(file)

    # Generate the public URL for the uploaded file
    url = blob.public_url

    #the ML open file from bucket URL
    image_bytes = requests.get(url)
    img = Image.open(io.BytesIO(image_bytes.content))
    img = img.resize((224,224), Image.NEAREST)
    pred_img = predict_label(img)

    

     # Generate UUID for the document in Firestore
    uuid = str(uuid4())

    # Check if user data already exists in Firestore
    users_ref = db.collection('users')
    query = users_ref.where('user_id', '==', request.user_id).limit(1)
    existing_data = list(query.stream()) 

     # Initialize the data dictionary
    data = {}

    if existing_data:
        # Iterate over the existing user data (assuming there is only one)
        for doc in existing_data:
            existing_doc = doc.to_dict()
            existing_plant_list = existing_doc.get('plant', [])
            if isinstance(existing_plant_list, dict):
                existing_plant_list = [existing_plant_list]
            # Determine the index for the new plant
            new_plant_index = len(existing_plant_list)

            # Create data object to be stored in Firestore with the new plant
            data = {
                'uuid': uuid,
                'user_id': request.user_id,
                'email': request.email,
                'name': request.username,
                'plant': [
                    {
                        'index': new_plant_index,
                        'image_url': url,
                        'name': pred_img
                    }
                ]
            }

            # Add the new plant to the existing plant list
            existing_plant_list.append(data['plant'][0])

            # Update the existing data with the updated plant list
            doc.reference.update({'plant': existing_plant_list})

            # Update the index of existing plants in the list
            for i, plant in enumerate(existing_plant_list):
                plant['index'] = i

            # Update the data object with the updated plant list
            data['plant'] = existing_plant_list

    else:
        # Create data object to be stored in Firestore with initial plant
        data = {
            'uuid': uuid,
            'user_id': request.user_id,
            'email': request.email,
            'name': request.username,
            'plant': [
                {
                    'index': 0,
                    'image_url': url,
                    'name': pred_img
                }
            ]
        }

        # Save data to Firestore
        users_ref.document(uuid).set(data)

    # Create the response data
    response_data = {
        'data': data,
        'message': 'Success',
        'error': False,
    }

    return jsonify(response_data), 200

@app.route("/register", methods=["POST"])
def register():
    email = request.json.get("email")
    password = request.json.get("password")
    display_name = request.json.get("display_name")

    try:
        auth.create_user(
            email=email,
            password=password,
            display_name=display_name
        )
        return jsonify({"error": False, "message": "Registration successful"}), 200
    except Exception as e:
        error_message = str(e)
        return jsonify({'error': 'Registration failed', 'message': error_message}), 400

#this function is only for backend debugging       
def create_custom_token(uid):
    custom_token = auth.create_custom_token(uid)
    return custom_token

@app.route('/signin', methods=['POST'])
def signin():
    email = request.json['email']
    user = auth.get_user_by_email(email)
    if user:
        try:
            custom_token = create_custom_token(user.uid)
            return {'token': custom_token.decode('utf-8')}
        except ValueError:
            return {'error': 'Invalid password'}
    else:
        return {'error': 'User not found'}
    
   
   
@app.route("/user/<user_id>", methods=["GET"])
@validate_token
def get_user_data(user_id):
    # Check if user ID matches the authenticated user
    if user_id != request.user_id:
        return jsonify({"error": True, "message": "Unauthorized"}), 403

    # Retrieve user data from Firestore
    users_ref = db.collection('users')
    query = users_ref.where('user_id', '==', user_id).limit(1)
    user_data = list(query.stream()) 

    if user_data:
        # Iterate over the user data (assuming there is only one)
        for doc in user_data:
            user_doc = doc.to_dict()
            # Retrieve the plant list for the user
            plant_list = user_doc.get('plant', [])

            if isinstance(plant_list, dict):
                plant_list = [plant_list]

            # Update the index values of the plant list
            for i, plant in enumerate(plant_list):
                plant['index'] = i

            response_data = {
                'message': 'User retrieved successfully',
                'error': False,
                'data': {
                    'user_id': user_id,
                    'email': request.email,
                    'name': request.username,
                    'plant': plant_list
                }
            }

            return jsonify(response_data), 200
    else:
        return jsonify({"error": True, "message": "User not found"}), 404


@app.route("/user/<user_id>/plant/<int:plant_index>", methods=["DELETE"])
@validate_token
def delete_plant(user_id, plant_index):
    # Check if user ID matches the authenticated user
    if user_id != request.user_id:
        return jsonify({"error": True, "message": "Unauthorized"}), 403

    # Retrieve user data from Firestore
    users_ref = db.collection('users')
    query = users_ref.where('user_id', '==', user_id).limit(1)
    user_data = query.stream()

    if user_data:
        # Iterate over the user data (assuming there is only one)
        for doc in user_data:
            user_doc_ref = doc.reference
            user_doc_data = doc.to_dict()
            plant_list = user_doc_data.get('plant', [])

            if isinstance(plant_list, dict):
                plant_list = [plant_list]

            # Check if the provided plant index is valid
            if plant_index < 0 or plant_index >= len(plant_list):
                return jsonify({"error": True, "message": "Invalid plant index"}), 400

            # Remove the plant at the specified index
            deleted_plant = plant_list.pop(plant_index)

            # Update the index values of the remaining plants in the list
            for i, plant in enumerate(plant_list):
                plant['index'] = i

            # Update the plant list in the user's document
            user_doc_ref.update({'plant': plant_list})

            response_data = {
                'message': 'Plant deleted',
                'error': False,
                'data': deleted_plant
            }

            return jsonify(response_data), 200
    else:
        return jsonify({"error": True, "message": "User not found"}), 404

@app.route("/user/<user_id>/plants", methods=["GET"])
@validate_token
def get_plants(user_id):
    # Check if user ID matches the authenticated user
    if user_id != request.user_id:
        return jsonify({"error": True, "message": "Unauthorized"}), 403

    # Retrieve user data from Firestore
    users_ref = db.collection('users')
    query = users_ref.where('user_id', '==', user_id).limit(1)
    user_data = query.stream()

    if user_data:
        # Iterate over the user data (assuming there is only one)
        for doc in user_data:
            user_doc_data = doc.to_dict()
            plant_list = user_doc_data.get('plant', [])

            if isinstance(plant_list, dict):
                plant_list = [plant_list]

            # Update the index values of the plant list
            for i, plant in enumerate(plant_list):
                plant['index'] = i

            if len(plant_list) == 0:
                return jsonify({"message": "No plants found", "error": False, "data": []}), 200

            response_data = {
                'message': 'Plants retrieved successfully',
                'error': False,
                'data': plant_list
            }

            return jsonify(response_data), 200
    else:
        return jsonify({"error": True, "message": "User not found"}), 404


if __name__ == "__main__":
    app.run(debug=True)