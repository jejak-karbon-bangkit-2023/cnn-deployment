# Flask RESTful API with Image Detection, Firebase Authentication, Firestore, and Google Storage

This project is a Flask RESTful API that provides image detection using TensorFlow and a pre-trained model in the .h5 format. It also includes a secure authentication system using Firebase JWT tokens. The data is stored in Google Cloud Firestore, and files can be uploaded and retrieved from Google Cloud Storage.

## Features

- Image detection using TensorFlow and a pre-trained model in the .h5 format.
- Secure authentication system using Firebase JWT tokens.
- Data storage using Google Cloud Firestore.
- File storage and retrieval using Google Cloud Storage.

## Requirements

Make sure you have the following installed:

- Python 3.x
- TensorFlow
- Flask
- Firebase Admin SDK
- Google Cloud Firestore Client Library
- Google Cloud Storage Client Library

# My Flask REST API

This is a Flask REST API that provides endpoints for managing users.

## Endpoints

### Register Users

Creates a new user.

- **URL**: `/register`
- **Method**: `POST`
- **Request Body**:
    ```json
    {
        "email": "user@example.com",
        "password": "password123",
        "display_name": "John Doe"
    }
    ```

- **Response**:
    - Status: 200 Created
    - Body:
        ```json
        {
            "error": false,
            "message": "Registration successful"
        }
        ```
Content-Type: application/json

### Predict Image

Predicts the content of an image using an H5 model. The file will store in the Google Bucket and the data 
will be writen in the firestore include the url of the image.

- **URL**: `/predict`
- **Method**: `POST`
- **Authentication**: Bearer Token
- **Request Headers**:
    - `Authorization`: Bearer Token (e.g., `Authorization: Bearer {token}`)

- **Request Body**:
    - Content-Type: `multipart/form-data`
    - Form Fields:
        - `file`: File field containing the image to predict.

- **Response**:
    - Status: 200 OK
    - Body:
        ```json
        {
            "prediction": "cat"
        }
