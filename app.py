from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import db
import zoho_crm

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'overseas_portal_2024')

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Fixed list of 10 top study-abroad destinations shown in the registration dropdown
PREFERRED_COUNTRIES = [
    'United States', 'United Kingdom', 'Canada', 'Australia', 'Switzerland',
    'Germany', 'Netherlands', 'New Zealand', 'Ireland', 'Sweden',
]

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name        = request.form['name']
        email       = request.form['email']
        password    = generate_password_hash(request.form['password'])
        study_level = request.form['study_level']
        country     = request.form['country']
        course      = request.form['course']
        phone       = request.form.get('phone', '').strip() or None

        conn_id = db.get_connection()
        cur_id  = conn_id.cursor()
        cur_id.execute('SELECT COUNT(*) + 1001 FROM students')
        student_id = cur_id.fetchone()[0]
        cur_id.close()
        db.release_connection(conn_id)

        image_path = None
        file = request.files.get('image')
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            image_path = filename

        conn = db.get_connection()
        cur = conn.cursor()
        try:
            cur.execute('''
                INSERT INTO students (name, email, password, student_id, study_level, country, course, image_path, phone)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (name, email, password, student_id, study_level, country, course, image_path, phone))
            conn.commit()
            flash('Registration successful! Please login.', 'success')
            try:
                zoho_crm.create_lead(name, email, course, country, study_level, phone)
            except Exception:
                pass  # don't block registration if Zoho fails
            return redirect(url_for('login'))
        except Exception:
            conn.rollback()
            flash('Email already exists or an error occurred.', 'error')
        finally:
            cur.close()
            db.release_connection(conn)     # return connection back to pool

    return render_template('register.html', countries=PREFERRED_COUNTRIES)


@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email    = request.form['email']
        password = request.form['password']

        conn = db.get_connection()
        cur = conn.cursor()
        cur.execute('SELECT * FROM students WHERE email = %s', (email,))
        student = cur.fetchone()
        cur.close()
        db.release_connection(conn)         # return connection back to pool

        if student and check_password_hash(student[3], password):
            session['student_id']    = student[0]
            session['student_name']  = student[1]
            session['study_level']   = student[5]
            flash(f'Welcome, {student[1]}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.', 'error')

    return render_template('login.html')


@app.route('/dashboard')
def dashboard():
    if 'student_id' not in session:
        return redirect(url_for('login'))

    conn = db.get_connection()
    cur  = conn.cursor()

    # Fetch this student's preferred country and study level
    cur.execute('SELECT country, study_level FROM students WHERE id = %s', (session['student_id'],))
    row = cur.fetchone()
    preferred_country = (row[0] or '').strip()
    study_level = (row[1] or '').strip()

    # ── Query 1: Universities in the preferred country filtered by study level ──
    # Columns: id[0] name[1] website[2] ranking[3] city[4] country[5]
    #          tuition_fee_usd[6] scholarship_info[7]
    preferred_unis = []
    if preferred_country:
        if study_level:
            cur.execute('''
                SELECT DISTINCT col.id, col.name, col.website, col.ranking,
                       cit.name AS city, ctr.name AS country,
                       col.tuition_fee_usd, col.scholarship_info
                FROM   colleges col
                JOIN   cities    cit ON col.city_id    = cit.id
                JOIN   states    st  ON cit.state_id   = st.id
                JOIN   countries ctr ON st.country_id  = ctr.id
                JOIN   courses   crs ON crs.college_id = col.id
                WHERE  LOWER(ctr.name)  = LOWER(%s)
                AND    LOWER(crs.level) = LOWER(%s)
                ORDER  BY col.ranking ASC NULLS LAST, col.name ASC
            ''', (preferred_country, study_level))
        else:
            cur.execute('''
                SELECT col.id, col.name, col.website, col.ranking,
                       cit.name AS city, ctr.name AS country,
                       col.tuition_fee_usd, col.scholarship_info
                FROM   colleges col
                JOIN   cities    cit ON col.city_id   = cit.id
                JOIN   states    st  ON cit.state_id  = st.id
                JOIN   countries ctr ON st.country_id = ctr.id
                WHERE  LOWER(ctr.name) = LOWER(%s)
                ORDER  BY col.ranking ASC NULLS LAST, col.name ASC
            ''', (preferred_country,))
        preferred_unis_raw = cur.fetchall()

        # Fetch all courses for those universities in one query
        courses_map = {}
        if preferred_unis_raw:
            uni_ids = [u[0] for u in preferred_unis_raw]
            cur.execute('''
                SELECT college_id, level, name, duration
                FROM   courses
                WHERE  college_id = ANY(%s)
                ORDER  BY college_id,
                    CASE level WHEN 'Bachelors' THEN 1 WHEN 'Masters' THEN 2
                               WHEN 'PhD' THEN 3 ELSE 4 END,
                    name
            ''', (uni_ids,))
            for row in cur.fetchall():
                courses_map.setdefault(row[0], []).append(
                    {'level': row[1], 'name': row[2], 'duration': row[3]}
                )
        preferred_unis = [u + (courses_map.get(u[0], []),) for u in preferred_unis_raw]

    # ── Query 2: ALL countries that have at least one college ─────────────────
    # No exclusion — we show every destination as a visual tile on the dashboard.
    # The preferred country is highlighted inside the grid with a badge.
    cur.execute('''
        SELECT DISTINCT ctr.id, ctr.name
        FROM   countries ctr
        JOIN   states    st  ON st.country_id = ctr.id
        JOIN   cities    cit ON cit.state_id  = st.id
        JOIN   colleges  col ON col.city_id   = cit.id
        ORDER  BY ctr.name
    ''')
    other_countries = cur.fetchall()

    cur.close()
    db.release_connection(conn)

    # Optionally load all student records when ?show=1 is in the URL
    students = []
    if request.args.get('show'):
        conn = db.get_connection()
        cur  = conn.cursor()
        cur.execute('''
            SELECT id, name, email, student_id, study_level, country, course, image_path, created_at
            FROM   students ORDER BY created_at DESC
        ''')
        students = cur.fetchall()
        cur.close()
        db.release_connection(conn)

    return render_template('dashboard.html',
                           students=students,
                           preferred_country=preferred_country,
                           preferred_unis=preferred_unis,
                           other_countries=other_countries,
                           study_level=study_level)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


def api_login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'student_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated


# ── Auth APIs ──────────────────────────────────────────────────────────────────

@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    required = ['name', 'email', 'password', 'study_level', 'country', 'course']
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({'error': f'Missing fields: {", ".join(missing)}'}), 400

    password = generate_password_hash(data['password'])
    conn = db.get_connection()
    cur = conn.cursor()
    try:
        cur.execute('SELECT COUNT(*) + 1001 FROM students')
        student_id = cur.fetchone()[0]
        cur.execute('''
            INSERT INTO students (name, email, password, student_id, study_level, country, course)
            VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
        ''', (data['name'], data['email'], password, student_id,
              data['study_level'], data['country'], data['course']))
        new_id = cur.fetchone()[0]
        conn.commit()
        return jsonify({'message': 'Registration successful', 'id': new_id, 'student_id': student_id}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 409
    finally:
        cur.close()
        db.release_connection(conn)         # return connection back to pool


@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({'error': 'email and password required'}), 400

    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM students WHERE email = %s', (data['email'],))
    student = cur.fetchone()
    cur.close()
    db.release_connection(conn)             # return connection back to pool

    if student and check_password_hash(student[3], data['password']):
        session['student_id']   = student[0]
        session['student_name'] = student[1]
        session['study_level']  = student[5]
        return jsonify({
            'message': f'Welcome, {student[1]}!',
            'student': {
                'id': student[0], 'name': student[1], 'email': student[2],
                'student_id': student[4], 'study_level': student[5],
                'country': student[6], 'course': student[7],
                'image_path': student[8]
            }
        }), 200

    return jsonify({'error': 'Invalid email or password'}), 401


@app.route('/api/logout', methods=['POST'])
def api_logout():
    session.clear()
    return jsonify({'message': 'Logged out successfully'}), 200


# ── Student APIs ───────────────────────────────────────────────────────────────

@app.route('/api/profile', methods=['GET'])
@api_login_required
def api_profile():
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute('''
        SELECT id, name, email, student_id, study_level, country, course, image_path, created_at
        FROM students WHERE id = %s
    ''', (session['student_id'],))
    s = cur.fetchone()
    cur.close()
    db.release_connection(conn)             # return connection back to pool

    if not s:
        return jsonify({'error': 'Student not found'}), 404

    return jsonify({
        'id': s[0], 'name': s[1], 'email': s[2], 'student_id': s[3],
        'study_level': s[4], 'country': s[5], 'course': s[6],
        'image_path': s[7], 'created_at': str(s[8])
    }), 200


@app.route('/api/students', methods=['GET'])
@api_login_required
def api_get_students():
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute('''
        SELECT id, name, email, student_id, study_level, country, course, image_path, created_at
        FROM students ORDER BY created_at DESC
    ''')
    rows = cur.fetchall()
    cur.close()
    db.release_connection(conn)             # return connection back to pool

    students = [
        {'id': r[0], 'name': r[1], 'email': r[2], 'student_id': r[3],
         'study_level': r[4], 'country': r[5], 'course': r[6],
         'image_path': r[7], 'created_at': str(r[8])}
        for r in rows
    ]
    return jsonify(students), 200


@app.route('/api/students/<int:student_id>', methods=['GET'])
@api_login_required
def api_get_student(student_id):
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute('''
        SELECT id, name, email, student_id, study_level, country, course, image_path, created_at
        FROM students WHERE id = %s
    ''', (student_id,))
    s = cur.fetchone()
    cur.close()
    db.release_connection(conn)             # return connection back to pool

    if not s:
        return jsonify({'error': 'Student not found'}), 404

    return jsonify({
        'id': s[0], 'name': s[1], 'email': s[2], 'student_id': s[3],
        'study_level': s[4], 'country': s[5], 'course': s[6],
        'image_path': s[7], 'created_at': str(s[8])
    }), 200


@app.route('/api/students/<int:student_id>', methods=['PUT'])
@api_login_required
def api_update_student(student_id):
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    fields = ['name', 'study_level', 'country', 'course']
    updates = {f: data[f] for f in fields if f in data}
    if not updates:
        return jsonify({'error': 'No valid fields to update'}), 400

    set_clause = ', '.join(f'{k} = %s' for k in updates)
    values = list(updates.values()) + [student_id]

    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute(f'UPDATE students SET {set_clause} WHERE id = %s', values)
    conn.commit()
    updated = cur.rowcount
    cur.close()
    db.release_connection(conn)             # return connection back to pool

    if updated == 0:
        return jsonify({'error': 'Student not found'}), 404
    return jsonify({'message': 'Student updated successfully'}), 200


@app.route('/api/universities/by-country/<int:country_id>')
@api_login_required
def api_universities_by_country(country_id):
    """Returns colleges for a country filtered by the logged-in student's study level,
    each with a nested list of all available courses."""
    study_level = session.get('study_level', '')
    conn = db.get_connection()
    cur  = conn.cursor()
    if study_level:
        cur.execute('''
            SELECT DISTINCT col.id, col.name, col.website, col.ranking,
                   cit.name AS city, ctr.name AS country,
                   col.tuition_fee_usd, col.scholarship_info
            FROM   colleges col
            JOIN   cities    cit ON col.city_id    = cit.id
            JOIN   states    st  ON cit.state_id   = st.id
            JOIN   countries ctr ON st.country_id  = ctr.id
            JOIN   courses   crs ON crs.college_id = col.id
            WHERE  ctr.id = %s
            AND    LOWER(crs.level) = LOWER(%s)
            ORDER  BY col.ranking ASC NULLS LAST, col.name ASC
        ''', (country_id, study_level))
    else:
        cur.execute('''
            SELECT col.id, col.name, col.website, col.ranking,
                   cit.name AS city, ctr.name AS country,
                   col.tuition_fee_usd, col.scholarship_info
            FROM   colleges col
            JOIN   cities    cit ON col.city_id   = cit.id
            JOIN   states    st  ON cit.state_id  = st.id
            JOIN   countries ctr ON st.country_id = ctr.id
            WHERE  ctr.id = %s
            ORDER  BY col.ranking ASC NULLS LAST, col.name ASC
        ''', (country_id,))
    rows = cur.fetchall()

    # Fetch all courses for these universities in one query
    courses_map = {}
    if rows:
        uni_ids = [r[0] for r in rows]
        cur.execute('''
            SELECT college_id, level, name, duration
            FROM   courses
            WHERE  college_id = ANY(%s)
            ORDER  BY college_id,
                CASE level WHEN 'Bachelors' THEN 1 WHEN 'Masters' THEN 2
                           WHEN 'PhD' THEN 3 ELSE 4 END,
                name
        ''', (uni_ids,))
        for row in cur.fetchall():
            courses_map.setdefault(row[0], []).append(
                {'level': row[1], 'name': row[2], 'duration': row[3]}
            )

    cur.close()
    db.release_connection(conn)

    return jsonify([
        {'id': r[0], 'name': r[1], 'website': r[2], 'ranking': r[3],
         'city': r[4], 'country': r[5],
         'tuition_fee_usd': r[6], 'scholarship_info': r[7],
         'courses': courses_map.get(r[0], [])}
        for r in rows
    ]), 200


@app.route('/api/students/<int:student_id>', methods=['DELETE'])
@api_login_required
def api_delete_student(student_id):
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute('DELETE FROM students WHERE id = %s', (student_id,))
    conn.commit()
    deleted = cur.rowcount
    cur.close()
    db.release_connection(conn)             # return connection back to pool

    if deleted == 0:
        return jsonify({'error': 'Student not found'}), 404
    return jsonify({'message': 'Student deleted successfully'}), 200


# ── Developer Panel ────────────────────────────────────────────────────────────

def dev_login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('dev_logged_in'):
            return redirect(url_for('dev_login'))
        return f(*args, **kwargs)
    return decorated


@app.route('/dev', methods=['GET', 'POST'])
@app.route('/dev/login', methods=['GET', 'POST'])
def dev_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = db.get_connection()
        cur  = conn.cursor()
        cur.execute('SELECT id, username, password FROM admins WHERE username = %s', (username,))
        admin = cur.fetchone()
        cur.close()
        db.release_connection(conn)

        if admin and check_password_hash(admin[2], password):
            session['dev_logged_in'] = True
            session['dev_username']  = admin[1]
            return redirect(url_for('dev_dashboard'))
        flash('Wrong username or password.', 'error')

    return render_template('dev_login.html')


@app.route('/dev/logout')
def dev_logout():
    session.pop('dev_logged_in', None)
    session.pop('dev_username',  None)
    return redirect(url_for('dev_login'))


@app.route('/dev/dashboard')
@dev_login_required
def dev_dashboard():
    conn = db.get_connection()
    cur  = conn.cursor()
    cur.execute('''
        SELECT id, name, email, student_id, study_level, country, course, image_path, created_at
        FROM students
        ORDER BY created_at DESC
    ''')
    students = cur.fetchall()
    cur.execute('SELECT COUNT(*) FROM students')
    total = cur.fetchone()[0]
    cur.close()
    db.release_connection(conn)
    return render_template('dev_dashboard.html', students=students, total=total)


@app.route('/dev/students/<int:sid>/edit', methods=['GET', 'POST'])
@dev_login_required
def dev_edit(sid):
    if request.method == 'POST':
        conn = db.get_connection()
        cur  = conn.cursor()
        try:
            cur.execute('''
                UPDATE students
                SET name=%s, email=%s, study_level=%s, country=%s, course=%s
                WHERE id=%s
            ''', (
                request.form['name'],
                request.form['email'],
                request.form['study_level'],
                request.form['country'],
                request.form['course'],
                sid
            ))
            conn.commit()
            flash('Student updated successfully.', 'success')
        except Exception:
            conn.rollback()
            flash('Update failed — email may already be in use.', 'error')
        finally:
            cur.close()
            db.release_connection(conn)
        return redirect(url_for('dev_dashboard'))

    conn = db.get_connection()
    cur  = conn.cursor()
    cur.execute('''
        SELECT id, name, email, student_id, study_level, country, course
        FROM students WHERE id = %s
    ''', (sid,))
    student = cur.fetchone()
    cur.close()
    db.release_connection(conn)

    if not student:
        flash('Student not found.', 'error')
        return redirect(url_for('dev_dashboard'))

    return render_template('dev_edit.html', student=student)


@app.route('/dev/students/<int:sid>/delete', methods=['POST'])
@dev_login_required
def dev_delete(sid):
    conn = db.get_connection()
    cur  = conn.cursor()
    cur.execute('DELETE FROM students WHERE id = %s', (sid,))
    conn.commit()
    cur.close()
    db.release_connection(conn)
    flash('Student deleted.', 'success')
    return redirect(url_for('dev_dashboard'))


# ── College Directory Routes ───────────────────────────────────────────────────

@app.route('/dev/countries', methods=['GET', 'POST'])
@dev_login_required
def dev_countries():
    if request.method == 'POST':
        name = request.form['name'].strip()
        conn = db.get_connection()
        cur  = conn.cursor()
        try:
            cur.execute('INSERT INTO countries (name) VALUES (%s)', (name,))
            conn.commit()
            flash(f'{name} added.', 'success')
        except Exception:
            conn.rollback()
            flash('Country already exists.', 'error')
        finally:
            cur.close()
            db.release_connection(conn)
        return redirect(url_for('dev_countries'))

    conn = db.get_connection()
    cur  = conn.cursor()
    cur.execute('SELECT id, name FROM countries ORDER BY name')
    countries = cur.fetchall()
    cur.close()
    db.release_connection(conn)
    return render_template('dev_countries.html', countries=countries)


@app.route('/dev/countries/<int:cid>/delete', methods=['POST'])
@dev_login_required
def dev_delete_country(cid):
    conn = db.get_connection()
    cur  = conn.cursor()
    cur.execute('DELETE FROM countries WHERE id = %s', (cid,))
    conn.commit()
    cur.close()
    db.release_connection(conn)
    flash('Country deleted.', 'success')
    return redirect(url_for('dev_countries'))


@app.route('/dev/states', methods=['GET', 'POST'])
@dev_login_required
def dev_states():
    if request.method == 'POST':
        name       = request.form['name'].strip()
        country_id = request.form['country_id']
        conn = db.get_connection()
        cur  = conn.cursor()
        try:
            cur.execute('INSERT INTO states (name, country_id) VALUES (%s, %s)', (name, country_id))
            conn.commit()
            flash(f'{name} added.', 'success')
        except Exception:
            conn.rollback()
            flash('Error adding state.', 'error')
        finally:
            cur.close()
            db.release_connection(conn)
        return redirect(url_for('dev_states'))

    conn = db.get_connection()
    cur  = conn.cursor()
    cur.execute('SELECT id, name FROM countries ORDER BY name')
    countries = cur.fetchall()
    cur.execute('''
        SELECT states.id, states.name, countries.name
        FROM states
        JOIN countries ON states.country_id = countries.id
        ORDER BY countries.name, states.name
    ''')
    states = cur.fetchall()
    cur.close()
    db.release_connection(conn)
    return render_template('dev_states.html', states=states, countries=countries)


@app.route('/dev/states/<int:sid>/delete', methods=['POST'])
@dev_login_required
def dev_delete_state(sid):
    conn = db.get_connection()
    cur  = conn.cursor()
    cur.execute('DELETE FROM states WHERE id = %s', (sid,))
    conn.commit()
    cur.close()
    db.release_connection(conn)
    flash('State deleted.', 'success')
    return redirect(url_for('dev_states'))


@app.route('/dev/cities', methods=['GET', 'POST'])
@dev_login_required
def dev_cities():
    if request.method == 'POST':
        name     = request.form['name'].strip()
        state_id = request.form['state_id']
        conn = db.get_connection()
        cur  = conn.cursor()
        try:
            cur.execute('INSERT INTO cities (name, state_id) VALUES (%s, %s)', (name, state_id))
            conn.commit()
            flash(f'{name} added.', 'success')
        except Exception:
            conn.rollback()
            flash('Error adding city.', 'error')
        finally:
            cur.close()
            db.release_connection(conn)
        return redirect(url_for('dev_cities'))

    conn = db.get_connection()
    cur  = conn.cursor()
    cur.execute('''
        SELECT states.id, states.name, countries.name
        FROM states
        JOIN countries ON states.country_id = countries.id
        ORDER BY countries.name, states.name
    ''')
    states = cur.fetchall()
    cur.execute('''
        SELECT cities.id, cities.name, states.name, countries.name
        FROM cities
        JOIN states    ON cities.state_id   = states.id
        JOIN countries ON states.country_id = countries.id
        ORDER BY countries.name, states.name, cities.name
    ''')
    cities = cur.fetchall()
    cur.close()
    db.release_connection(conn)
    return render_template('dev_cities.html', cities=cities, states=states)


@app.route('/dev/cities/<int:cid>/delete', methods=['POST'])
@dev_login_required
def dev_delete_city(cid):
    conn = db.get_connection()
    cur  = conn.cursor()
    cur.execute('DELETE FROM cities WHERE id = %s', (cid,))
    conn.commit()
    cur.close()
    db.release_connection(conn)
    flash('City deleted.', 'success')
    return redirect(url_for('dev_cities'))


@app.route('/dev/colleges', methods=['GET', 'POST'])
@dev_login_required
def dev_colleges():
    if request.method == 'POST':
        conn = db.get_connection()
        cur  = conn.cursor()
        try:
            ranking  = request.form.get('ranking', '').strip()
            tuition  = request.form.get('tuition_fee_usd', '').strip()
            cur.execute('''
                INSERT INTO colleges
                    (name, description, website, city_id, ranking, tuition_fee_usd, scholarship_info)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', (
                request.form['name'].strip(),
                request.form['description'].strip(),
                request.form['website'].strip(),
                request.form['city_id'],
                int(ranking) if ranking.isdigit() else None,
                int(tuition) if tuition.isdigit() else None,
                request.form.get('scholarship_info', '').strip() or None,
            ))
            conn.commit()
            flash(f'{request.form["name"]} added.', 'success')
        except Exception:
            conn.rollback()
            flash('Error adding college.', 'error')
        finally:
            cur.close()
            db.release_connection(conn)
        return redirect(url_for('dev_colleges'))

    conn = db.get_connection()
    cur  = conn.cursor()
    cur.execute('''
        SELECT cities.id, cities.name, states.name, countries.name
        FROM cities
        JOIN states    ON cities.state_id   = states.id
        JOIN countries ON states.country_id = countries.id
        ORDER BY countries.name, states.name, cities.name
    ''')
    cities = cur.fetchall()
    # id[0] name[1] website[2] ranking[3] tuition[4] scholarship[5] city[6] state[7] country[8]
    cur.execute('''
        SELECT colleges.id, colleges.name, colleges.website, colleges.ranking,
               colleges.tuition_fee_usd, colleges.scholarship_info,
               cities.name, states.name, countries.name
        FROM colleges
        JOIN cities    ON colleges.city_id  = cities.id
        JOIN states    ON cities.state_id   = states.id
        JOIN countries ON states.country_id = countries.id
        ORDER BY countries.name, colleges.name
    ''')
    colleges = cur.fetchall()
    cur.close()
    db.release_connection(conn)
    return render_template('dev_colleges.html', colleges=colleges, cities=cities)


@app.route('/dev/colleges/<int:cid>/edit', methods=['GET', 'POST'])
@dev_login_required
def dev_edit_college(cid):
    if request.method == 'POST':
        conn = db.get_connection()
        cur  = conn.cursor()
        try:
            ranking  = request.form.get('ranking', '').strip()
            tuition  = request.form.get('tuition_fee_usd', '').strip()
            cur.execute('''
                UPDATE colleges
                SET name=%s, description=%s, website=%s, city_id=%s,
                    ranking=%s, tuition_fee_usd=%s, scholarship_info=%s
                WHERE id=%s
            ''', (
                request.form['name'],
                request.form['description'],
                request.form['website'],
                request.form['city_id'],
                int(ranking) if ranking.isdigit() else None,
                int(tuition) if tuition.isdigit() else None,
                request.form.get('scholarship_info', '').strip() or None,
                cid
            ))
            conn.commit()
            flash('College updated.', 'success')
        except Exception:
            conn.rollback()
            flash('Update failed.', 'error')
        finally:
            cur.close()
            db.release_connection(conn)
        return redirect(url_for('dev_colleges'))

    conn = db.get_connection()
    cur  = conn.cursor()
    # id[0] name[1] description[2] website[3] city_id[4] ranking[5] tuition[6] scholarship[7]
    cur.execute('''
        SELECT id, name, description, website, city_id, ranking, tuition_fee_usd, scholarship_info
        FROM colleges WHERE id=%s
    ''', (cid,))
    college = cur.fetchone()
    cur.execute('''
        SELECT cities.id, cities.name, states.name, countries.name
        FROM cities
        JOIN states    ON cities.state_id   = states.id
        JOIN countries ON states.country_id = countries.id
        ORDER BY countries.name, states.name, cities.name
    ''')
    cities = cur.fetchall()
    cur.close()
    db.release_connection(conn)
    if not college:
        flash('College not found.', 'error')
        return redirect(url_for('dev_colleges'))
    return render_template('dev_edit_college.html', college=college, cities=cities)


@app.route('/dev/colleges/<int:cid>/delete', methods=['POST'])
@dev_login_required
def dev_delete_college(cid):
    conn = db.get_connection()
    cur  = conn.cursor()
    cur.execute('DELETE FROM colleges WHERE id = %s', (cid,))
    conn.commit()
    cur.close()
    db.release_connection(conn)
    flash('College deleted.', 'success')
    return redirect(url_for('dev_colleges'))


@app.route('/dev/courses', methods=['GET', 'POST'])
@dev_login_required
def dev_courses():
    if request.method == 'POST':
        conn = db.get_connection()
        cur  = conn.cursor()
        try:
            cur.execute('''
                INSERT INTO courses (name, level, fee_per_year, currency, duration, description, college_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', (
                request.form['name'].strip(),
                request.form['level'],
                request.form['fee_per_year'],
                request.form['currency'],
                request.form['duration'].strip(),
                request.form['description'].strip(),
                request.form['college_id']
            ))
            conn.commit()
            flash(f'{request.form["name"]} added.', 'success')
        except Exception:
            conn.rollback()
            flash('Error adding course.', 'error')
        finally:
            cur.close()
            db.release_connection(conn)
        return redirect(url_for('dev_courses'))

    conn = db.get_connection()
    cur  = conn.cursor()
    cur.execute('''
        SELECT colleges.id, colleges.name, countries.name
        FROM colleges
        JOIN cities    ON colleges.city_id  = cities.id
        JOIN states    ON cities.state_id   = states.id
        JOIN countries ON states.country_id = countries.id
        ORDER BY countries.name, colleges.name
    ''')
    colleges = cur.fetchall()
    cur.execute('''
        SELECT courses.id, courses.name, courses.level, courses.fee_per_year,
               courses.currency, courses.duration, colleges.name, countries.name
        FROM courses
        JOIN colleges  ON courses.college_id = colleges.id
        JOIN cities    ON colleges.city_id   = cities.id
        JOIN states    ON cities.state_id    = states.id
        JOIN countries ON states.country_id  = countries.id
        ORDER BY countries.name, colleges.name, courses.name
    ''')
    courses = cur.fetchall()
    cur.close()
    db.release_connection(conn)
    return render_template('dev_courses.html', courses=courses, colleges=colleges)


@app.route('/dev/courses/<int:cid>/edit', methods=['GET', 'POST'])
@dev_login_required
def dev_edit_course(cid):
    if request.method == 'POST':
        conn = db.get_connection()
        cur  = conn.cursor()
        try:
            cur.execute('''
                UPDATE courses
                SET name=%s, level=%s, fee_per_year=%s, currency=%s,
                    duration=%s, description=%s, college_id=%s
                WHERE id=%s
            ''', (
                request.form['name'],
                request.form['level'],
                request.form['fee_per_year'],
                request.form['currency'],
                request.form['duration'],
                request.form['description'],
                request.form['college_id'],
                cid
            ))
            conn.commit()
            flash('Course updated.', 'success')
        except Exception:
            conn.rollback()
            flash('Update failed.', 'error')
        finally:
            cur.close()
            db.release_connection(conn)
        return redirect(url_for('dev_courses'))

    conn = db.get_connection()
    cur  = conn.cursor()
    cur.execute('''
        SELECT id, name, level, fee_per_year, currency, duration, description, college_id
        FROM courses WHERE id=%s
    ''', (cid,))
    course = cur.fetchone()
    cur.execute('''
        SELECT colleges.id, colleges.name, countries.name
        FROM colleges
        JOIN cities    ON colleges.city_id  = cities.id
        JOIN states    ON cities.state_id   = states.id
        JOIN countries ON states.country_id = countries.id
        ORDER BY countries.name, colleges.name
    ''')
    colleges = cur.fetchall()
    cur.close()
    db.release_connection(conn)
    if not course:
        flash('Course not found.', 'error')
        return redirect(url_for('dev_courses'))
    return render_template('dev_edit_course.html', course=course, colleges=colleges)


@app.route('/dev/courses/<int:cid>/delete', methods=['POST'])
@dev_login_required
def dev_delete_course(cid):
    conn = db.get_connection()
    cur  = conn.cursor()
    cur.execute('DELETE FROM courses WHERE id = %s', (cid,))
    conn.commit()
    cur.close()
    db.release_connection(conn)
    flash('Course deleted.', 'success')
    return redirect(url_for('dev_courses'))


# ── Zoho CRM OAuth Routes ──────────────────────────────────────────────────────

@app.route('/zoho/auth')
def zoho_auth():
    auth_url = (
        'https://accounts.zoho.com/oauth/v2/auth'
        '?scope=ZohoCRM.modules.leads.CREATE'
        f'&client_id={zoho_crm.CLIENT_ID}'
        '&response_type=code'
        '&access_type=offline'
        f'&redirect_uri={zoho_crm.REDIRECT_URI}'
    )
    return redirect(auth_url)


@app.route('/zoho/callback')
def zoho_callback():
    code = request.args.get('code')
    if not code:
        return 'Error: No code received from Zoho.', 400
    result = zoho_crm.exchange_code_for_tokens(code)
    if result.get('refresh_token'):
        return 'Zoho connected successfully! You can close this tab.'
    return f'Something went wrong: {result}', 400


if __name__ == '__main__':
    db.create_table()
    db.create_admin_table()
    db.insert_default_admin()
    db.create_countries_table()
    db.create_states_table()
    db.create_cities_table()
    db.create_colleges_table()
    db.add_ranking_to_colleges()
    db.create_courses_table()
    db.seed_data()
    db.seed_courses()
    db.seed_expanded_courses()
    app.run(debug=True)
