from flask import Flask, render_template, request, flash, redirect, url_for, session
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, TextAreaField, HiddenField
from wtforms.validators import DataRequired, Length, EqualTo
from werkzeug.security import check_password_hash
from functools import wraps
from model import evaluate_diary
from database import init_db, add_user, get_user, add_diary, get_all_diaries, get_diary, update_diary, delete_diary, get_diaries_for_month, check_table_structure, get_diary_count_for_today
import calendar
from datetime import datetime, date

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'

# アプリケーション起動時にデータベースを初期化
init_db()
check_table_structure()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('ログインが必要です。', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

class RegistrationForm(FlaskForm):
    username = StringField('ユーザー名', validators=[DataRequired(), Length(min=4, max=25)])
    password = PasswordField('パスワード', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('パスワード（確認）', validators=[DataRequired(), EqualTo('password')])

class LoginForm(FlaskForm):
    username = StringField('ユーザー名', validators=[DataRequired()])
    password = PasswordField('パスワード', validators=[DataRequired()])

class DiaryForm(FlaskForm):
    title = StringField('タイトル', validators=[Length(max=100)])
    diary = TextAreaField('日記', validators=[DataRequired(), Length(max=500)])

class EditDiaryForm(FlaskForm):
    id = HiddenField('ID')
    title = StringField('タイトル', validators=[Length(max=100)])
    diary = TextAreaField('日記', validators=[DataRequired(), Length(max=500)])

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        if get_user(username):
            flash('そのユーザー名は既に使用されています。', 'error')
        else:
            add_user(username, password)
            flash('アカウントが作成されました。ログインしてください。', 'success')
            return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = get_user(form.username.data)
        if user:
            if check_password_hash(user[2], form.password.data):
             session['user_id'] = user[0]
             flash('ログインしました。', 'success')
             return redirect(url_for('home'))
            else:
             flash('パスワードが正しくありません。', 'error')
        else:
           flash('ユーザー名が見つかりません。', 'error')
    return render_template('login.html', form=form)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('ログアウトしました。', 'success')
    return redirect(url_for('home'))

@app.route('/')
@login_required
def home():
    return render_template('home.html')

@app.route('/create', methods=['GET', 'POST'])
@login_required
def create_diary():
    form = DiaryForm()
    if form.validate_on_submit():
        title = form.title.data
        diary_text = form.diary.data
        try:
            user_id = session.get('user_id')
            if not user_id:
                raise ValueError("User ID not found in session")
            
            diary_count = get_diary_count_for_today(user_id)
            if diary_count >= 3:
                flash('本日の日記の制限（3つ）に達しました。既存の日記を削除してから新しい日記を書いてください。', 'warning')
                return redirect(url_for('diary_calendar'))
            
            sentiment_label, score = evaluate_diary(diary_text)
            if add_diary(user_id, title, diary_text, sentiment_label, score):
                flash('日記が保存されました。', 'success')
            else:
                flash('日記の保存に失敗しました。', 'error')
            return redirect(url_for('diary_calendar'))
        except Exception as e:
            flash(f'エラーが発生しました: {str(e)}', 'error')
    return render_template('create_diary.html', form=form)

@app.route('/calendar')
@login_required
def diary_calendar():
    user_id = session.get('user_id')
    year = int(request.args.get('year', datetime.now().year))
    month = int(request.args.get('month', datetime.now().month))
    cal = calendar.monthcalendar(year, month)

    try:
        diaries = get_diaries_for_month(user_id, year, month)
        today = datetime.now().strftime('%Y-%m-%d')
        today_count = get_diary_count_for_today(user_id)  
        can_add_diary = today_count < 3
    except Exception as e:
        app.logger.error(f"Error fetching diaries: {e}", exc_info=True)
        flash('日記の取得中にエラーが発生しました。', 'error')
        diaries = {}
        today = datetime.now().strftime('%Y-%m-%d')
        today_count = 0
        can_add_diary = False

    return render_template('diary_calendar.html', 
                           year=year, 
                           month=month, 
                           calendar=cal, 
                           diaries=diaries, 
                           today=today,
                           can_add_diary=can_add_diary,
                           today_count=today_count)

@app.route('/diary/<date>')
@login_required
def diary_detail(date):
    diaries = get_all_diaries(session['user_id']).get(date, {'entries': []})
    return render_template('diary_detail.html', date=date, diaries=diaries)

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_diary(id):
    diary = get_diary(id, session['user_id'])
    if diary is None:
        flash('日記が見つかりません。', 'error')
        return redirect(url_for('diary_calendar'))
    
    form = EditDiaryForm(id=id, title=diary[2] or '', diary=diary[3])  # diary[2] は title, diary[3] は content
    
    if form.validate_on_submit():
        title = form.title.data
        content = form.diary.data
        sentiment_label, score = evaluate_diary(content)
        update_diary(id, session['user_id'], title, content, sentiment_label, score)
        flash('日記が更新されました。', 'success')
        return redirect(url_for('diary_calendar'))
    
    return render_template('edit_diary.html', form=form, diary=diary)

@app.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete_diary_route(id):
    user_id = session.get('user_id')
    diary = get_diary(id, user_id)
    if diary is None:
        flash('日記が見つかりません。', 'error')
    else:
        delete_diary(id, user_id)
        flash('日記が削除されました。', 'success')
    return redirect(url_for('diary_calendar'))

@app.template_filter('today')
def today_filter(format='%Y-%m-%d'):
    return datetime.now().strftime(format)

if __name__ == '__main__':
    app.run(debug=True)