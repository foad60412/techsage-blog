from app import db, Article, get_setting
from openai import OpenAI
import os

def generate_articles():
    api_key = get_setting("openai_api_key")
    if not api_key:
        print("❌ No OpenAI API key found.")
        return

    client = OpenAI(api_key=api_key)

    prompts = [
        "Write a short blog post (300 words) about a trending AI tool in 2025.",
        "Write a tech blog post (300 words) about how AI improves productivity at work.",
        "Write a blog post (300 words) comparing two AI writing tools."
    ]

    for prompt in prompts:
        try:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a helpful blog writer."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=700
            )

            content = response.choices[0].message.content.strip()
            title = content.split('.')[0][:100]

            article = Article(title=title, content=content)
            db.session.add(article)

        except Exception as e:
            print("❌ Error generating article:", e)

    db.session.commit()
    print("✅ 3 articles generated successfully.")
