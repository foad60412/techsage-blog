from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from config import Config
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from sqlalchemy import text
import requests
import openai
import os

app = Flask(__name__)
app.config.from_object(Config)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ======= Models =======
class AdminUser(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    likes = db.Column(db.Integer, default=0)

class Visit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    article_id = db.Column(db.Integer, db.ForeignKey('article.id'), nullable=True)
    timestamp = db.Column(db.DateTime, server_default=db.func.now())

class Setting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=False)

class SocialLink(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    platform = db.Column(db.String(50), unique=True)
    url = db.Column(db.String(255))
    visible = db.Column(db.Boolean, default=True)
class Ad(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    position = db.Column(db.String(50), nullable=False)
    content = db.Column(db.Text, nullable=False)
    enabled = db.Column(db.Boolean, default=True)

# ======= Helpers =======
def get_setting(key, default=None):
    setting = Setting.query.filter_by(key=key).first()
    return setting.value if setting else default

def set_setting(key, value):
    setting = Setting.query.filter_by(key=key).first()
    if setting:
        setting.value = value
    else:
        setting = Setting(key=key, value=value)
        db.session.add(setting)
    db.session.commit()

@login_manager.user_loader
def load_user(user_id):
    return AdminUser.query.get(int(user_id))

def fetch_image_for_title(title):
    api_key = get_setting("pexels_api_key")
    if not api_key:
        return None
    headers = {"Authorization": api_key}
    params = {"query": title, "per_page": 1}
    response = requests.get("https://api.pexels.com/v1/search", headers=headers, params=params)
    if response.status_code == 200:
        data = response.json()
        if data["photos"]:
            return data["photos"][0]["src"]["large"]
    return None
def get_ads_by_position(position):
    return Ad.query.filter_by(position=position, enabled=True).all()

# ======= Routes =======
@app.route('/')
def index():
    db.session.add(Visit(article_id=None))
    db.session.commit()

    query = request.args.get('q')
    filter_by = request.args.get('sort', 'latest')

    if filter_by == 'likes':
        order = Article.likes.desc()
    elif filter_by == 'views':
        order = db.func.count(Visit.id).desc()
    else:
        order = Article.created_at.desc()

    base_query = Article.query
    if query:
        base_query = base_query.filter(Article.title.ilike(f"%{query}%"))

    if filter_by == 'views':
        articles = db.session.query(Article).outerjoin(Visit).group_by(Article.id).order_by(order).all()
    else:
        articles = base_query.order_by(order).all()

    popular_articles = db.session.query(Article.id, Article.title, db.func.count(Visit.id).label('views'))\
        .join(Visit, Article.id == Visit.article_id)\
        .group_by(Article.id).order_by(db.desc('views')).limit(5).all()

    social_links = SocialLink.query.filter_by(visible=True).all()
    top_ads = get_ads_by_position("top")
    bottom_ads = get_ads_by_position("bottom")

    return render_template('index.html', articles=articles, popular_articles=popular_articles, social_links=social_links, top_ads=top_ads, bottom_ads=bottom_ads)

@app.route('/article/<int:article_id>')
def read_article(article_id):
    article = Article.query.get_or_404(article_id)
    db.session.add(Visit(article_id=article.id))
    db.session.commit()

    social_links = SocialLink.query.filter_by(visible=True).all()
    sidebar_ads = get_ads_by_position("sidebar")
    in_article_ads = get_ads_by_position("in-article")

    # إضافة مقالات مقترحة بشكل عشوائي مع استثناء المقال الحالي
    suggested_articles = Article.query.filter(Article.id != article.id).order_by(db.func.random()).limit(3).all()

    # شريط المقالات الأكثر مشاهدة
    popular_articles = db.session.query(Article.id, Article.title, db.func.count(Visit.id).label('views'))\
        .join(Visit, Article.id == Visit.article_id)\
        .group_by(Article.id)\
        .order_by(db.desc('views'))\
        .limit(5).all()

    return render_template(
        'read_article.html',
        article=article,
        social_links=social_links,
        sidebar_ads=sidebar_ads,
        in_article_ads=in_article_ads,
        suggested_articles=suggested_articles,
        popular_articles=popular_articles
    )

@app.route('/admin/ads', methods=['GET', 'POST'])
@login_required
def manage_ads():
    if request.method == 'POST':
        position = request.form['position']
        content = request.form['content']
        enabled = 'enabled' in request.form
        ad = Ad(position=position, content=content, enabled=enabled)
        db.session.add(ad)
        db.session.commit()
        flash("Ad saved successfully!", "success")
        return redirect(url_for('manage_ads'))
    ads = Ad.query.order_by(Ad.id.desc()).all()
    return render_template("admin_ads.html", ads=ads)

@app.route('/admin/delete_ad/<int:ad_id>')
@login_required
def delete_ad(ad_id):
    ad = Ad.query.get_or_404(ad_id)
    db.session.delete(ad)
    db.session.commit()
    flash("Ad deleted successfully!", "success")
    return redirect(url_for('manage_ads'))

@app.route('/admin/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = AdminUser.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid login credentials", "danger")
    return render_template('admin_login.html')

@app.route('/admin/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/admin/dashboard')
@login_required
def dashboard():
    total_articles = Article.query.count()
    total_visits = Visit.query.count()
    total_comments = 0
    popular_articles = db.session.query(Article.title, db.func.count(Visit.id).label('views')).join(Visit, Article.id == Visit.article_id).group_by(Article.id).order_by(db.desc('views')).limit(5).all()
    return render_template('admin_dashboard.html', total_articles=total_articles, total_visits=total_visits, total_comments=total_comments, popular_articles=popular_articles)

@app.route('/admin/settings', methods=['GET', 'POST'])
@login_required
def settings():
    openai_key = get_setting("openai_api_key", "")
    pexels_key = get_setting("pexels_api_key", "")
    if request.method == 'POST':
        set_setting("openai_api_key", request.form['openai_api_key'])
        set_setting("pexels_api_key", request.form['pexels_api_key'])
        current_pass = request.form.get('current_password')
        new_pass = request.form.get('new_password')
        if current_pass and new_pass:
            admin = AdminUser.query.get(current_user.id)
            if check_password_hash(admin.password, current_pass):
                admin.password = generate_password_hash(new_pass)
                db.session.commit()
                flash("Password changed successfully.", "success")
            else:
                flash("Current password is incorrect.", "danger")
        flash("Settings saved successfully.", "success")
        return redirect(url_for('settings'))
    return render_template("admin_settings.html", openai_key=openai_key, pexels_key=pexels_key)

@app.route('/admin/generate_article', methods=['POST'])
@login_required
def generate_article():
    try:
        client = openai.OpenAI(api_key=get_setting("openai_api_key"))
        prompt = "Write a blog post about a trending technology topic in 2025. Make it informative and engaging."
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
        flash("✅ Article generated successfully!", "success")
    except Exception as e:
        flash(f"❌ Error generating article: {e}", "danger")
    return redirect(url_for('dashboard'))

@app.route('/admin/create', methods=['GET', 'POST'])
@login_required
def create_article():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        image_url = fetch_image_for_title(title)
        new_article = Article(title=title, content=content, image_url=image_url)
        db.session.add(new_article)
        db.session.commit()
        flash('Article created successfully!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('create_article.html')

@app.route('/admin/articles')
@login_required
def manage_articles():
    per_page = 5
    page = request.args.get('page', 1, type=int)
    total_articles = Article.query.count()
    total_pages = (total_articles + per_page - 1) // per_page
    articles = Article.query.order_by(Article.created_at.desc()).offset((page-1)*per_page).limit(per_page).all()
    return render_template('admin_manage_articles.html',
                           articles=articles,
                           page=page,
                           per_page=per_page,
                           total_pages=total_pages)

@app.route('/admin/edit/<int:article_id>', methods=['GET', 'POST'])
@login_required
def edit_article(article_id):
    article = Article.query.get_or_404(article_id)
    if request.method == 'POST':
        article.title = request.form['title']
        article.content = request.form['content']
        db.session.commit()
        flash('Article updated successfully.', 'success')
        return redirect(url_for('manage_articles'))
    return render_template('admin_edit_article.html', article=article)

@app.route('/admin/delete/<int:article_id>', methods=['POST'])
@login_required
def delete_article(article_id):
    article = Article.query.get_or_404(article_id)
    db.session.delete(article)
    db.session.commit()
    flash('Article deleted successfully.', 'success')
    return redirect(url_for('manage_articles'))

@app.route('/admin/analytics')
@login_required
def analytics():
    return render_template("admin_analytics.html")

@app.route('/admin/analytics/data')
@login_required
def analytics_data():
    range_type = request.args.get("range", "daily")
    now = datetime.utcnow()
    if range_type == "daily":
        start = now - timedelta(days=7)
        format_label = "%Y-%m-%d"
    elif range_type == "weekly":
        start = now - timedelta(weeks=12)
        format_label = "Week %U"
    elif range_type == "monthly":
        start = now - timedelta(days=365)
        format_label = "%Y-%m"
    else:
        return jsonify({})
    visits = Visit.query.filter(Visit.timestamp >= start).all()
    stats = {}
    for visit in visits:
        label = visit.timestamp.strftime(format_label)
        stats[label] = stats.get(label, 0) + 1
    labels = sorted(stats.keys())
    values = [stats[label] for label in labels]
    return jsonify({"labels": labels, "data": values})

@app.route('/admin/social', methods=['GET', 'POST'])
@login_required
def social_links():
    platforms = ['Facebook', 'Twitter', 'Instagram', 'YouTube', 'TikTok']
    existing = {s.platform: s for s in SocialLink.query.all()}
    if request.method == 'POST':
        for platform in platforms:
            url = request.form.get(f"{platform}_url")
            visible = bool(request.form.get(f"{platform}_visible"))
            if platform in existing:
                existing[platform].url = url
                existing[platform].visible = visible
            else:
                db.session.add(SocialLink(platform=platform, url=url, visible=visible))
        db.session.commit()
        flash("Social links updated successfully.", "success")
        return redirect(url_for('social_links'))
    return render_template("admin_social_links.html", social_links=existing, platforms=platforms)

@app.route('/like/<int:article_id>', methods=['POST'])
def like_article(article_id):
    article = Article.query.get_or_404(article_id)
    article.likes = (article.likes or 0) + 1
    db.session.commit()
    return jsonify({'success': True, 'likes': article.likes})
@app.route('/admin/generate_article_api', methods=['POST'])
@login_required
def generate_article_api():
    try:
        # استخدام مفتاح OpenAI من الإعدادات
        client = openai.OpenAI(api_key=get_setting("openai_api_key"))
        prompt = "Write a unique, trending technology blog post for 2025. Include a catchy title and an engaging introduction."
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        content = response.choices[0].message.content.strip()
        # استخراج العنوان: أول سطر/سطر بعلامة #
        lines = content.split("\n")
        title = ""
        for line in lines:
            if line.strip() and not title:
                # إذا يبدأ بـ # فهو عنوان
                if line.strip().startswith("#"):
                    title = line.strip("# ").strip()
                else:
                    title = line.strip()
        if not title:
            title = "Tech Blog Article"
        return jsonify({"success": True, "title": title, "content": content})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
    
@app.route('/sw.js')
def service_worker():
    return app.send_static_file('sw.js')

if __name__ == '__main__':
    os.makedirs('database', exist_ok=True)
    with app.app_context():
        db.create_all()
    app.run(debug=True)
