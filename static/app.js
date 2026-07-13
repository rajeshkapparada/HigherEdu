// ── Login ──────────────────────────────────────────────────────────────────────
async function login(email, password) {
    const res = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
    });
    const data = await res.json();

    if (res.ok) {
        alert(`Welcome, ${data.student.name}!`);
        window.location.href = '/dashboard';
    } else {
        alert(data.error);  // 'Invalid email or password'
    }
}


// ── Register ───────────────────────────────────────────────────────────────────
async function register(formData) {
    const res = await fetch('/api/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
        // formData = { name, email, password, student_id, study_level, country, course }
    });
    const data = await res.json();

    if (res.ok) {
        alert('Registration successful! Please login.');
        window.location.href = '/login';
    } else {
        alert(data.error);  // 'Email already exists or a database error occurred'
    }
}


// ── Logout ─────────────────────────────────────────────────────────────────────
async function logout() {
    const res = await fetch('/api/logout', { method: 'POST' });
    const data = await res.json();
    alert(data.message);
    window.location.href = '/login';
}


// ── Get all students ───────────────────────────────────────────────────────────
async function getAllStudents() {
    const res = await fetch('/api/students');
    if (res.status === 401) { window.location.href = '/login'; return; }
    return await res.json();  // returns array of student objects
}


// ── Search students (mirrors dashboard search in app.py) ───────────────────────
async function searchStudents(query, field) {
    const allStudents = await getAllStudents();
    if (!allStudents) return [];

    return allStudents.filter(student => {
        const value = String(student[field] || '').toLowerCase();
        if (field === 'student_id') {
            return value === String(query);           // exact match (same as CAST = %s)
        }
        return value.includes(query.toLowerCase());   // partial match (same as ILIKE %%)
    });
}


// ── Get one student ────────────────────────────────────────────────────────────
async function getStudent(id) {
    const res = await fetch(`/api/students/${id}`);
    if (!res.ok) { alert('Student not found'); return null; }
    return await res.json();
}


// ── Update student ─────────────────────────────────────────────────────────────
async function updateStudent(id, updates) {
    // updates = { name, study_level, country, course }  (only these 4 allowed)
    const res = await fetch(`/api/students/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates)
    });
    const data = await res.json();
    alert(data.message || data.error);
}


// ── Delete student ─────────────────────────────────────────────────────────────
async function deleteStudent(id) {
    const res = await fetch(`/api/students/${id}`, { method: 'DELETE' });
    const data = await res.json();
    alert(data.message || data.error);
}


// ── Get my profile ─────────────────────────────────────────────────────────────
async function getMyProfile() {
    const res = await fetch('/api/profile');
    if (res.status === 401) { window.location.href = '/login'; return; }
    return await res.json();
}
