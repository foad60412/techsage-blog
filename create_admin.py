import os
from werkzeug.security import generate_password_hash
from app import app, db, AdminUser

# تأكد من أن مجلد قاعدة البيانات موجود
os.makedirs('database', exist_ok=True)

with app.app_context():
    try:
        db.create_all()  # إنشاء الجداول
    except Exception as e:
        print(f"❌ خطأ أثناء إنشاء قاعدة البيانات: {e}")
        exit()

    email = "admin@gmail.com"
    password = "Fiuw2212"

    # تحقق من وجود الأدمن مسبقًا
    if AdminUser.query.filter_by(email=email).first():
        print("⚠️ الأدمن موجود بالفعل.")
    else:
        hashed_password = generate_password_hash(password)
        admin = AdminUser(email=email, password=hashed_password)
        db.session.add(admin)
        db.session.commit()
        print("✅ تم إنشاء الأدمن بنجاح!")