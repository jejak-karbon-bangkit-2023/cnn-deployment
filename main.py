from logging import exception
import os
import io
import requests
import tensorflow
from tensorflow import keras
import numpy as np
from PIL import Image
from flask import Flask, request, jsonify
from google.cloud import firestore, storage
import firebase_admin
from firebase_admin import auth, credentials
from uuid import uuid4
from functools import wraps
from flask_restful import Api

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'config/service-account.json'

cred = credentials.Certificate('config/service-account.json')
firebase_admin.initialize_app(cred)

# The `project` parameter is optional and represents which project the client
# will act on behalf of. If not supplied, the client falls back to the default
# project inferred from the environment.


model = keras.models.load_model("model.h5")
label = ['Pohon Beringin','Pohon Bungur','Pohon Cassia','Pohon Jati','Pohon Kenanga','Pohon Kerai Payung','Pohon Saga','Pohon Trembesi','pohon Mahoni','pohon Matoa']

app = Flask(__name__)
#declaration using firestore and storage bucket
db = firestore.Client(project='jejak-karbon-bangkit23')
storage_client = storage.Client(project='jejak-karbon-bangkit23')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def convert_to_jpg(file):
    image = Image.open(file)
    if image.mode != 'RGB':
        image = image.convert('RGB')
    image_jpg = io.BytesIO()
    image.save(image_jpg, format='JPEG')
    image_jpg.seek(0)
    return image_jpg

# Function to get the next available index for a username
def get_next_index(username, dir):
    # Get the bucket reference
    bucket = storage.Client().bucket(dir)

    # Create the subdirectory based on the username
    subdirectory = f"{username}/"

    # List the objects in the subdirectory
    blobs = bucket.list_blobs(prefix=subdirectory)

    # Get the maximum index from the existing objects
    max_index = -1
    for blob in blobs:
        filename = blob.name.split('/')[-1]
        index = int(filename.split('.')[0])
        if index > max_index:
            max_index = index

    # Calculate the next available index
    next_index = max_index + 1 if max_index >= 0 else 0

    return next_index

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
        except firebase_admin.auth.ExpiredIdTokenError:
            return jsonify({"error": "Expired authorization token"}), 401

        return f(*args, **kwargs)
    return decorated_function

def absorption_count(plant):
    if plant == 'Pohon Beringin':
        return 218.9
    elif plant == 'Pohon Bungur':
        return 27.97
    elif plant == 'Pohon Cassia':
        return 0.96
    elif plant == 'Pohon Jati':
        return 23.63
    elif plant == 'Pohon Kenanga':
        return 7.9
    elif plant == 'Pohon Kerai Payung':
        return 4.15
    elif plant == 'Pohon Saga':
        return 2.6
    elif plant == 'Pohon Trembesi':
        return 23.33
    elif plant == 'Pohon Mahoni':
        return 51.66
    elif plant == 'Pohon Matoa':
        return 1356.05
    else:
        return None
    
def emission_count(plant, distance):
    if plant == 'Sepeda Motor':
        ems = 103
    elif plant == 'Mobil':
        ems = 192
    elif plant == 'Bis':
        ems = 105
    else:
        ems = 0
    hasil = ems * distance
    return hasil

#route of post image
@app.route("/predict", methods=["POST"])
@validate_token
def predict():
    file = request.files.get('file')
    

    if file is None or file.filename == "":
        return jsonify({"error": "no file"})
    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file format'}), 400
    # Create the subdirectory based on the username
    subdirectory = f"{request.user_id}/"
    
    index = get_next_index(request.user_id,'img-plant')

    # Generate the file name with the .jpg format
    filename = f"{index}.jpg"

    # Convert the file to .jpg if it's in .png or .jpeg format
    if file.filename.lower().endswith(('.png', '.jpeg')):
        file = convert_to_jpg(file)
    

    # Upload the file to Google Cloud Storage
    bucket = storage_client.bucket('img-plant')
    blob = bucket.blob(subdirectory + filename)
    blob.upload_from_file(file)

    # Generate the public URL for the uploaded file
    url = blob.public_url

    #the ML open file from bucket URL
    image_bytes = requests.get(url)
    img = Image.open(io.BytesIO(image_bytes.content))
    img = img.resize((224,224), Image.NEAREST)
    pred_img = predict_label(img)

    c_in = absorption_count(pred_img)

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
                        'name': pred_img,
                        'c_in': c_in
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
                    'name': pred_img,
                    'c_in': c_in
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
    try:     
        user = auth.get_user_by_email(email)
        custom_token = create_custom_token(user.uid)
        return {'token': custom_token.decode('utf-8')}, 200
    except Exception as e:
        return {'error': str(e)}, 500
    
 
   
@app.route("/user/<user_id>", methods=["GET"])
@validate_token
def get_user_data(user_id):
    try:
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
                transport_list= user_doc.get('transport', [])

                if isinstance(plant_list, dict):
                    plant_list = [plant_list]
                if isinstance(transport_list, dict):
                    transport_list = [transport_list]

                # Update the index values of the plant list
                for i, plant in enumerate(plant_list):
                    plant['index'] = i

                for i, transport in enumerate(transport_list):
                    transport['index'] = i

                response_data = {
                    'message': 'User retrieved successfully',
                    'error': False,
                    'data': {
                        'user_id': user_id,
                        'email': request.email,
                        'name': request.username,
                        'plant': plant_list,
                        'transport':transport_list

                    }
                }

                return jsonify(response_data), 200
        else:
            return jsonify({"error": True, "message": "User not found"}), 404
    except Exception as e:
        return {'error': str(e)}, 500

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

            # Get the bucket reference
            bucket = storage_client.bucket('img-plant')
            
            # Create the subdirectory based on the username
            subdirectory = f"{user_id}/"

            # Generate the file name
            filename = f"{plant_index}.jpg"
            
            # Delete the file from the subdirectory in the bucket
            blob = bucket.blob(subdirectory + filename)
            if bucket.get_blob(subdirectory+filename):
                blob.delete()
                # Update the index values or rename the remaining images
                blobs = bucket.list_blobs(prefix=subdirectory)
                for blob in blobs:
                    if blob.name != subdirectory + filename:
                        old_filename = blob.name.split('/')[-1]
                        old_index = int(old_filename.split('.')[0])
                        if old_index > plant_index:
                            new_index = old_index - 1
                            new_filename = f"{new_index}.jpg"
                            bucket.rename_blob(blob, new_name=subdirectory+new_filename)

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
    

@app.route("/emission",methods=["POST"])
@validate_token
def emission():
    trports= request.json.get("transport")
    distnce=request.json.get("distance")

    #{"Sepeda Motor", "Mobil", "Bis"}
    c_out=emission_count(trports,distnce)

     # Generate UUID for the document in Firestore
    uuid = str(uuid4())

    # Check if user data already exists in Firestore
    users_ref = db.collection('users')
    query = users_ref.where('user_id', '==', request.user_id).limit(1)
    existing_data = list(query.stream()) 

     # Initialize the data dictionary
    data = {}

    try:
        if existing_data:
            # Iterate over the existing user data (assuming there is only one)
            for doc in existing_data:
                existing_doc = doc.to_dict()
                existing_transport_list = existing_doc.get('transport', [])

                if isinstance(existing_transport_list, dict):
                    existing_transport_list = [existing_transport_list]

                # Determine the index for the new transport
                new_transport_index = len(existing_transport_list)

                # Create data object to be stored in Firestore with the new transport
                data = {
                            'uuid': uuid,
                            'user_id': request.user_id,
                            'email': request.email,
                            'name': request.username,
                            'transport': [
                            {
                                'index': new_transport_index,
                                'name' : trports,
                                'distance': distnce,
                                'c_out':c_out
                            }
                            ]
                            }

                # Add the new transport to the existing transport list
                existing_transport_list.append(data['transport'][0])

                # Update the existing data with the updated transport list
                doc.reference.update({'transport': existing_transport_list})

                # Update the index of existing transport in the list
                for i, transport in enumerate(existing_transport_list):
                    transport['index'] = i

                # Update the data object with the updated transport list
                data['transport'] = existing_transport_list

        else:
         # Create data object to be stored in Firestore with initial transport
            data = {
            'uuid': uuid,
            'user_id': request.user_id,
            'email': request.email,
            'name': request.username,
            'transport': [
                {   
                    'index':0,
                    'name' : trports,
                    'distance': distnce,
                    'c_out':c_out
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
        return jsonify(response_data),200
    except Exception as e:
        return {'error': str(e)}, 500

@app.route("/user/<user_id>/transport/<int:transport_index>", methods=["DELETE"])
@validate_token
def delete_transport(user_id, transport_index):
    # Check if user ID matches the authenticated user
    if user_id != request.user_id:
        return jsonify({"error": True, "message": "Unauthorized"}), 403

    # Retrieve user data from Firestore
    users_ref = db.collection('users')
    query = users_ref.where('user_id', '==', user_id).limit(1)
    user_data = query.stream()
    try:
        if user_data:
            # Iterate over the user data (assuming there is only one)
            for doc in user_data:
                user_doc_ref = doc.reference
                user_doc_data = doc.to_dict()
                transport_list = user_doc_data.get('transport', [])

                if isinstance(transport_list, dict):
                    transport_list = [transport_list]

                # Check if the provided transport index is valid
                if transport_index < 0 or transport_index >= len(transport_list):
                    return jsonify({"error": True, "message": "Invalid transport index"}), 400

                # Remove the transport at the specified index
                deleted_transport = transport_list.pop(transport_index)

                # Update the index values of the remaining transports in the list
                for i, transport in enumerate(transport_list):
                    transport['index'] = i

                # Update the transport list in the user's document
                user_doc_ref.update({'transport': transport_list})

                response_data = {
                    'message': 'Transport deleted',
                    'error': False,
                    'data': deleted_transport
                }
                
                return jsonify(response_data), 200
        else:
            return jsonify({"error": True, "message": "User not found"}), 404
    except Exception as e:
        return {'error': str(e)}, 500
    
@app.route("/user/<user_id>/transport", methods=["GET"])
@validate_token
def get_transport(user_id):
    # Check if user ID matches the authenticated user
    if user_id != request.user_id:
        return jsonify({"error": True, "message": "Unauthorized"}), 403

    # Retrieve user data from Firestore
    users_ref = db.collection('users')
    query = users_ref.where('user_id', '==', user_id).limit(1)
    user_data = query.stream()
    try:
        if user_data:
            # Iterate over the user data (assuming there is only one)
            for doc in user_data:
                user_doc_data = doc.to_dict()
                transport_list = user_doc_data.get('transport', [])

                if isinstance(transport_list, dict):
                    transport_list = [transport_list]

                # Update the index values of the transport list
                for i, transport in enumerate(transport_list):
                    transport['index'] = i

                if len(transport_list) == 0:
                    return jsonify({"message": "No transport found", "error": False, "data": []}), 200

                response_data = {
                    'message': 'Transport retrieved successfully',
                    'error': False,
                    'data': transport_list
                }

                return jsonify(response_data), 200
        else:
            return jsonify({"error": True, "message": "User not found"}), 404
    except Exception as e:
        return {'error': str(e)}, 500
                   
@app.route('/post_article', methods=['POST'])
def post_article():
    # Get the form data
    title = request.form.get('title')
    content = request.form.get('content')
    paragraphs = request.form.getlist('paragraphs[]')
    image = request.files.get('image')

    index = get_next_index('1010','article-img')
    filename=f"{index}.jpg"
    subdirectory= "1010/"
    # Upload the resized image to Google Cloud Storage
    bucket = storage_client.bucket('article-img')
    blob = bucket.blob(subdirectory+filename)
    blob.upload_from_file(image)

    # Generate the public URL for the uploaded image
    image_url = blob.public_url

    # Create a new document in Firestore
    doc_ref = db.collection('articles').document()

    # Prepare the article data
    article_data = {
        'title': title,
        'content': content,
        'paragraphs': paragraphs,
        'image_url': image_url
    }

    # Save the article data to Firestore
    doc_ref.set(article_data)

    # Prepare the response data
    response_data = {
        'id': doc_ref.id,
        'message': 'Article posted successfully'
    }

    # Return the response as JSON
    return jsonify(response_data), 200

@app.route('/articles', methods=['GET'])
def get_articles():
    # Retrieve all articles from Firestore
    articles = db.collection('articles').stream()

    articles_data = []
    for article in articles:
        # Extract the article ID and title
        article_data = {
            'id': article.id,
            'title': article.get('title'),
            'image_url':article.get('image_url')
        }
        articles_data.append(article_data)

    return jsonify(articles_data), 200

@app.route('/articles/<article_id>', methods=['GET'])
def get_article(article_id):
    # Retrieve the article from Firestore
    doc_ref = db.collection('articles').document(article_id)
    article = doc_ref.get()

    if article.exists:
        # Extract the article data
        article_data = article.to_dict()
        return jsonify(article_data), 200
    else:
        return jsonify({'error': 'Article not found'}), 404
    
@app.route('/articles/<article_id>', methods=['DELETE'])
def delete_article(article_id):
    # Get the document reference
    doc_ref = db.collection('articles').document(article_id)

    # Get the article data
    article_data = doc_ref.get().to_dict()

    if article_data:
        # Delete the document from Firestore
        doc_ref.delete()

        # Delete the corresponding file from Google Cloud Storage
        image_url = article_data.get('image_url')
        if image_url:
            # Extract the filename from the image URL
            filename = image_url.split('/')[-1]

            # Get the bucket reference
            bucket = storage_client.bucket('article-img')

            # Create the blob path based on the filename
            blob_path = f"1010/{filename}"

            if bucket.get_blob(blob_path):
                # Delete the blob from the bucket
                blob = bucket.blob(blob_path)
                blob.delete()

        # Prepare the response data
        response_data = {
            'id': article_id,
            'message': 'Article deleted successfully'
        }
        return jsonify(response_data), 200
    else:
        # If the article is not found, return a 404 response
        return jsonify({'error': 'Article not found'}), 404
        
if __name__ == "__main__":
    app.run(debug=True)