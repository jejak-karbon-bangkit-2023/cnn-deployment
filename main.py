import os

import io
import tensorflow
from tensorflow import keras
import numpy as np
from PIL import Image
from flask import Flask, request, jsonify

model = keras.models.load_model("model.h5")
label = ['Pohon Beringin','Pohon Bungur','Pohon Cassia','Pohon Jati','Pohon Kenanga','Pohon Kerai Payung','Pohon Saga','Pohon Trembesi','pohon Mahoni','pohon Matoa']

app = Flask(__name__)

def predict_label(img):
    i = np.asarray(img) / 255.0
    i = i.reshape(1, 224, 224, 3)
    pred = model.predict(i)
    result = label[np.argmax(pred)]
    return result

@app.route("/predict", methods=["GET", "POST"])
def index():
    file = request.files.get('file')
    if file is None or file.filename == "":
        return jsonify({"error": "no file"})
    
    image_bytes = file.read()
    img = Image.open(io.BytesIO(image_bytes))
    img = img.resize((224,224), Image.NEAREST)
    pred_img = predict_label(img)
    return pred_img

if __name__ == "__main__":
    app.run(debug=True)