from app import app
from ai.article_generator import generate_articles

with app.app_context():
    generate_articles()
