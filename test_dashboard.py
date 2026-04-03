from app import create_app
from models import db, User

app = create_app()
with app.app_context():
    user = User.query.filter_by(username='admin').first()
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
    response = client.get('/dashboard')
    print("STATUS:", response.status_code)
    try:
        print("BODY:", response.data.decode('utf-8')[:500])
    except Exception as e:
        print("ERROR:", e)
