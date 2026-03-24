from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy 
from datetime import datetime  
import uuid  
import os
from werkzeug.utils import secure_filename
from flask_migrate import Migrate
from urllib.parse import urlparse, parse_qs
import re

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///forum.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False


# ===== SECURITY IMPROVEMENT =====
app.config['SECRET_KEY'] = 'secretpassword'  # Required for flash messages
# ===== END ADDITION =====

db = SQLAlchemy(app)
migrate = Migrate(app, db)

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)  

import re

def extract_youtube_id(url):
    """Extract YouTube ID from various URL formats"""
    patterns = [
        r'(?:youtube\.com/(?:[^/]+/.+/|(?:v|e(?:mbed)?)/|.*[?&]v=)([^"&?/\s]{11}))',
        r'youtu\.be/([^"&?/\s]{11})',
        r'youtube\.com/embed/([^"&?/\s]{11})',
        r'youtube\.com/shorts/([^"&?/\s]{11})'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif', 'pdf'}

class Interview(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    youtube_url = db.Column(db.String(200), nullable=False)
    youtube_id = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Interview {self.title}>'

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    content = db.Column(db.Text, nullable=False)
    image = db.Column(db.String(200))
    publish_date = db.Column(db.DateTime, default=datetime.utcnow)
    comments = db.relationship('Comment', back_populates='post', cascade='all, delete-orphan')

class News(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False) 
    content = db.Column(db.Text, nullable=False)
    publish_date = db.Column(db.DateTime, default=datetime.utcnow)
    is_pinned = db.Column(db.Boolean, default=False)
    image = db.Column(db.String(200))  

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    event_type = db.Column(db.String(50))  
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime)
    location = db.Column(db.String(200))
    is_recurring = db.Column(db.Boolean, default=False)  
    image = db.Column(db.String(200))  

class LibraryBook(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(100))
    description = db.Column(db.Text)
    category = db.Column(db.String(50))  
    file_path = db.Column(db.String(200))
    cover_image = db.Column(db.String(200)) 
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_removed = db.Column(db.Boolean, default=False)  
    removal_reason = db.Column(db.Text)  
    post = db.relationship('Post', back_populates='comments')

class BlogPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    content = db.Column(db.Text, nullable=False)
    image = db.Column(db.String(200))
    publish_date = db.Column(db.DateTime, default=datetime.utcnow)
    is_pinned = db.Column(db.Boolean, default=False)
    comments = db.relationship('BlogComment', backref='post', lazy=True, cascade='all, delete-orphan')

class BlogComment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_removed = db.Column(db.Boolean, default=False)
    removal_reason = db.Column(db.Text)
    post_id = db.Column(db.Integer, db.ForeignKey('blog_post.id'), nullable=False)
    author = db.Column(db.String(100))  

@app.route("/")
def index():
    latest_post = Post.query.order_by(Post.publish_date.desc()).first()
    news_items = News.query.order_by(News.publish_date.desc()).limit(3).all()
    now = datetime.utcnow()
    next_event = Event.query.filter(Event.end_time > now).order_by(Event.start_time).first()
    latest_news = News.query.order_by(News.publish_date.desc()).limit(2).all()
    blog_posts = BlogPost.query.order_by(BlogPost.publish_date.desc()).all()
    recent_comments = BlogComment.query.order_by(BlogComment.created_at.desc()).limit(10).all()

    return render_template("index.html",
                        latest_post=latest_post,
                        next_event=next_event,
                        latest_news=latest_news,
                        blog_posts=blog_posts,
                        recent_comments=recent_comments)

@app.route('/admin', methods=['GET', 'POST'])
def admin_dashboard():
    if request.method == 'POST':
        if 'youtube_url' in request.form:
            url = request.form['youtube_url']
            youtube_id = extract_youtube_id(url)
            
            if not youtube_id:
                flash('Invalid YouTube URL', 'error')
                return redirect(url_for('admin_dashboard'))
    
    all_events = Event.query.order_by(Event.start_time.desc()).all()  

    posts = Post.query.with_entities(
        Post.id,
        Post.title,
        Post.publish_date,
    ).order_by(Post.publish_date.desc()).all()

    books = LibraryBook.query.order_by(LibraryBook.title).all()
    interviews = Interview.query.order_by(Interview.id).all()
    news_items = News.query.order_by(News.publish_date.desc()).all()
    blog_posts = BlogPost.query.order_by(BlogPost.publish_date.desc()).all()
    
    return render_template('admin_dashboard.html',
                        posts=posts,
                        books=books,
                        interviews=interviews,
                        news_items=news_items,
                        events=all_events,
                        blog_posts=blog_posts)

@app.route('/admin/delete_interview/<int:id>', methods=['POST'])
def delete_interview(id):
    interview = Interview.query.get_or_404(id)
    db.session.delete(interview)
    db.session.commit()
    return '', 204  

@app.route("/forum")
def forum():
    posts = Post.query.order_by(Post.publish_date.desc()).all()
    return render_template("forum.html", posts=posts)

@app.route("/post/<int:post_id>")
def post(post_id):
    post = Post.query.get_or_404(post_id)
    return render_template("post.html", post=post)

@app.route('/submit_post', methods=['GET', 'POST'])
def submit_post():
    if request.method == "POST":
        image_filename = None
        if 'image' in request.files:
            file = request.files['image']
            if file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_filename = filename
        
        new_post = Post(
            title=request.form["title"],
            description=request.form["description"],
            content=request.form["content"],
            image=image_filename
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("forum"))
    
    return render_template("submit_post.html")

@app.route('/admin/create_post', methods=['POST'])
def create_post():
    image_filename = None  
    if 'image' in request.files:
        file = request.files['image']
        if file.filename != '' and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            image_filename = filename
    
    new_post = Post(
        title=request.form["title"],
        description=request.form["description"],
        content=request.form["content"],
        image=image_filename
    )
    db.session.add(new_post)
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/edit_post/<int:post_id>', methods=['GET', 'POST'])
def edit_post(post_id):
    post = Post.query.get_or_404(post_id)
    if request.method == 'POST':
        post.title = request.form['title']
        post.description = request.form['description']
        post.content = request.form['content']
        
        if 'image' in request.files:
            file = request.files['image']
            if file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                post.image = filename
        
        db.session.commit()
        return redirect(url_for('admin_dashboard'))
    
    return render_template('edit_post.html', post=post)

@app.route("/playlist")
def playlist():
    return render_template("playlist.html")

@app.route('/post/<int:post_id>/comment', methods=['POST'])
def add_comment(post_id):
    comment = Comment(
        post_id=post_id,
        content=request.form['content']
    )
    db.session.add(comment)
    db.session.commit()
    return redirect(url_for('post', post_id=post_id))

@app.route('/admin/delete_comment/<int:comment_id>', methods=['POST'])
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    removal_reason = request.form.get('removal_reason', '')
    
    comment.is_removed = True
    comment.removal_reason = removal_reason
        
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_post/<int:post_id>')
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/events')
def manage_events():
    events = Event.query.order_by(Event.start_time).all()
    return render_template('admin_dashboard.html',
                         events=events,
                         active_tab='events')

@app.route("/library")
def library():
    books = LibraryBook.query.order_by(LibraryBook.title).all()
    return render_template("library.html", books=books)

@app.route('/admin/delete_book/<int:book_id>')
def delete_book(book_id):
    book = LibraryBook.query.get_or_404(book_id)
    
    try:
        # Delete PDF file
        pdf_path = os.path.join(app.static_folder, 'library/pdfs', book.file_path)
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        
        if book.cover_image:
            cover_path = os.path.join(app.static_folder, 'library/covers', book.cover_image)
            if os.path.exists(cover_path):
                os.remove(cover_path)
        
        db.session.delete(book)
        db.session.commit()
        
    except Exception as e:
        db.session.rollback()
    
    return redirect(url_for('admin_dashboard', _anchor='archives'))

@app.route('/upload_book', methods=['POST'])
def upload_book():
    if 'file' not in request.files:
        return redirect(request.url)
    
    file = request.files['file']
    if file.filename == '':
        return redirect(request.url)
    
    if file and allowed_file(file.filename):
        os.makedirs(os.path.join(app.static_folder, 'library/pdfs'), exist_ok=True)
        os.makedirs(os.path.join(app.static_folder, 'library/covers'), exist_ok=True)
        
        pdf_filename = secure_filename(file.filename)
        pdf_path = os.path.join('library/pdfs', pdf_filename)
        file.save(os.path.join(app.static_folder, pdf_path))
        
        cover_filename = None
        if 'cover' in request.files:
            cover = request.files['cover']
            if cover.filename != '' and allowed_file(cover.filename):
                cover_filename = secure_filename(cover.filename)
                cover_path = os.path.join('library/covers', cover_filename)
                cover.save(os.path.join(app.static_folder, cover_path))
        
        new_book = LibraryBook(
            title=request.form['title'],
            author=request.form['author'],
            description=request.form.get('description', ''),
            category=request.form.get('category', 'uncategorized'),
            file_path=pdf_filename,
            cover_image=cover_filename
        )
        db.session.add(new_book)
        db.session.commit()
    
    return redirect(url_for('admin_dashboard', _anchor='archives'))

@app.route('/interviews')
def interviews():
    all_interviews = Interview.query.order_by(Interview.created_at.desc()).all()
    return render_template('interviews.html', interviews=all_interviews)

@app.route('/interview/<int:id>')
def interview_detail(id):
    interview = Interview.query.get_or_404(id)
    return render_template('interview_detail.html', interview=interview)

@app.route('/admin/news', methods=['GET', 'POST'])
def admin_news():
    if request.method == 'POST':
        news_id = request.form.get('news_id')
        
        image_filename = None
        if 'image' in request.files:
            file = request.files['image']
            if file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_filename = filename
        
        if news_id:  
            news = News.query.get(news_id)
            if news:
                news.title = request.form['title']
                news.description = request.form['description']
                news.content = request.form['content']
                news.is_pinned = 'is_pinned' in request.form
                if image_filename:
                    news.image = image_filename
        else:  
            news = News(
                title=request.form['title'],
                description=request.form['description'],
                content=request.form['content'],
                is_pinned='is_pinned' in request.form,
                image=image_filename
            )
            db.session.add(news)
        
        db.session.commit()
        return redirect(url_for('admin_dashboard', _anchor='news'))
    
    return redirect(url_for('admin_dashboard'))

@app.route('/news')
def news():
    news_items = News.query.order_by(News.is_pinned.desc(), News.publish_date.desc()).all()
    return render_template('news.html', news_items=news_items)

@app.route('/news/<int:news_id>')
def news_article(news_id):
    news = News.query.get_or_404(news_id)
    return render_template('news_article.html', news=news)

@app.route('/admin/delete_news/<int:news_id>')
def delete_news(news_id):
    news = News.query.get_or_404(news_id)
    db.session.delete(news)
    db.session.commit()
    return redirect(url_for('admin_dashboard', _anchor='news'))

@app.route('/events')
def events():
    now = datetime.utcnow()
    upcoming = Event.query.filter(Event.start_time >= now).order_by(Event.start_time).all()
    return render_template('events.html', events=upcoming)

@app.route('/admin/add_event', methods=['POST'])
def add_event():
    if request.method == 'POST':
        event_id = request.form.get('event_id')
        
        if event_id:  
            event = Event.query.get(event_id)
            if not event:
                abort(404)
        else:  
            event = Event()
        
        event.title = request.form['title']
        event.description = request.form['description']
        event.event_type = request.form['event_type']
        event.start_time = datetime.strptime(request.form['start_time'], '%Y-%m-%dT%H:%M')
        event.end_time = datetime.strptime(request.form['end_time'], '%Y-%m-%dT%H:%M') if request.form['end_time'] else None
        event.location = request.form.get('location')
        event.is_recurring = 'is_recurring' in request.form
        
        db.session.add(event)
        db.session.commit()
        flash('Event saved successfully!', 'success')
        return redirect(url_for('admin_dashboard', _anchor='events'))

@app.route('/admin/delete_event/<int:id>', methods=['POST'])
def delete_event(id):
    event = Event.query.get_or_404(id)
    db.session.delete(event)
    db.session.commit()
    return '', 204

@app.route('/admin/add_blog', methods=['POST'])
def admin_add_blog():
    if request.method == 'POST':
        image_filename = None
        if 'image' in request.files:
            file = request.files['image']
            if file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_filename = filename
        
        blog_id = request.form.get('blog_id')
        if blog_id: 
            post = BlogPost.query.get(blog_id)
            if post:
                post.title = request.form['title']
                post.description = request.form['description']
                post.content = request.form['content']
                post.is_pinned = 'is_pinned' in request.form
                if image_filename:
                    post.image = image_filename
                db.session.commit()
                flash('Blog post updated successfully!', 'success')
        else:  
            post = BlogPost(
                title=request.form['title'],
                description=request.form['description'],
                content=request.form['content'],
                is_pinned='is_pinned' in request.form,
                image=image_filename
            )
            db.session.add(post)
            db.session.commit()
            flash('Blog post created successfully!', 'success')
    
    return redirect(url_for('admin_dashboard', _anchor='blog'))

@app.route('/admin/delete_blog/<int:post_id>')
def admin_delete_blog(post_id):
    post = BlogPost.query.get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()
    flash('Blog post deleted', 'success')
    return redirect(url_for('admin_dashboard', _anchor='blog'))

@app.route('/admin/remove_comment/<int:comment_id>', methods=['POST'])
def admin_remove_comment(comment_id):
    comment = BlogComment.query.get_or_404(comment_id)
    comment.is_removed = True
    comment.removal_reason = request.form.get('reason', 'Moderator removed')
    db.session.commit()
    return '', 204

@app.route("/blog")
def blog():
    posts = BlogPost.query.order_by(BlogPost.is_pinned.desc(), BlogPost.publish_date.desc()).all()
    return render_template("blog.html", posts=posts)

@app.route("/blog/<int:post_id>", methods=['GET', 'POST'])
def blog_post(post_id):
    post = BlogPost.query.get_or_404(post_id)
    if request.method == 'POST':
        content = request.form.get('content')
        if content:
            comment = BlogComment(
                content=content,
                post_id=post_id,
                author=request.form.get('name', 'Anonymous')
            )
            db.session.add(comment)
            db.session.commit()
            flash('Your comment has been posted!', 'success')
            return redirect(url_for('blog_post', post_id=post_id))
    
    return render_template("blog_post.html", post=post)

@app.route("/blog/comment", methods=["POST"])
def add_blog_comment():
    post_id = request.form.get('post_id')
    content = request.form.get('content')
    if post_id and content:
        comment = BlogComment(
            content=content,
            post_id=post_id,
            author=request.form.get('name', 'Anonymous')
        )
        db.session.add(comment)
        db.session.commit()
        flash('Comment added successfully!', 'success')
    return redirect(url_for('blog_post', post_id=post_id))

if __name__ == "__main__":
    app.run(host='127.0.0.1', port=5000, debug=True, use_reloader=False)
