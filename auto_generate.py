import os
from app import app, db, Article, fetch_image_for_title, get_setting
import openai
from datetime import datetime

# إعداد عميل OpenAI
client = openai.OpenAI(api_key=get_setting("openai_api_key"))

# التعليمات المرسلة إلى GPT
prompt = "Write a short, engaging blog post about a trending tech topic in 2025. Keep it under 300 words."

def generate_article():
    with app.app_context():
        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}]
            )
            content = response.choices[0].message.content.strip()
            title = content.split("\n")[0].strip("# ").strip()[:100]
            image_url = fetch_image_for_title(title)
            article = Article(title=title, content=content, image_url=image_url)
            db.session.add(article)
            db.session.commit()
            print(f"✅ [{datetime.now()}] Article created: {title}")
        except Exception as e:
            print(f"❌ Error: {e}")

# تشغيل السكريبت
if __name__ == "__main__":
    generate_article()
