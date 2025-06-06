from flask import Flask, render_template, request
from diffusers import StableDiffusionPipeline
import torch
import uuid

app = Flask(__name__)

# تحميل النموذج (مرة واحدة عند التشغيل)
pipe = StableDiffusionPipeline.from_pretrained(
    "runwayml/stable-diffusion-v1-5",
    torch_dtype=torch.float32,
).to("cpu")

@app.route("/", methods=["GET", "POST"])
def index():
    image_path = None
    if request.method == "POST":
        text = request.form.get("prompt")
        if text:
            # ترجمة النص للعربية باستخدام Google Translate (بسيطة ومؤقتة)
            from deep_translator import GoogleTranslator
            translated = GoogleTranslator(source='auto', target='en').translate(text)

            # توليد الصورة
            image = pipe(translated).images[0]
            filename = f"static/{uuid.uuid4().hex}.png"
            image.save(filename)
            image_path = filename
    return render_template("index.html", image=image_path)

if __name__ == "__main__":
    app.run(debug=True)
