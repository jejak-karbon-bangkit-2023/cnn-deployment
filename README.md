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
### Post an Article

Create a new article by sending a POST request to the following endpoint:

- **URL**: `/articles`
- **Method**: `POST`
- **Request Body**:
- `title` (string): The title of the article.
- `content` (string): The content of the article.
- `paragraphs` (array): An array of paragraphs in the article.
- `image` (file): The image file associated with the article.

- **Response**:
```json
{
  "id": "abc123",
  "message": "Article posted successfully"
}
```
### Get All Articles

Retrieve all articles by sending a GET request to the following endpoint:
- **URL**: `/articles`
- **Method**: `GET`
- **Response**:
```json
[
  {
    "id": "abc123",
    "title": "Sample Article 1"
  },
  {
    "id": "def456",
    "title": "Sample Article 2"
  }
]
```

### Get Article by ID
- **URL**: `/articles/<article_id>`
- **Method**: `GET`
- **Response**:
json```[
{
  "id": "abc123",
  "title": "Sample Article",
  "content": "Lorem ipsum dolor sit amet...",
  "paragraphs": [
    "Paragraph 1",
    "Paragraph 2",
    "Paragraph 3"
  ],
  "image_url": "https://storage.googleapis.com/article-img/1010/1.jpg"
}
]```

### Delete Article

Delete an article by its ID by sending a DELETE request to the following endpoint:

- **URL**: `/articles/<article_id>`
- **Method**: `DELETE`
- **Response**:
json```[
    {
  "id": "abc123",
  "message": "Article deleted successfully"
}
]```