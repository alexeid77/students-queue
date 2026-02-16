from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from models import Session as DBSession, Queue, QueueItem, init_db
from datetime import datetime, timezone
from functools import wraps

app = Flask(__name__)
app.secret_key = 'student-queue-secret-key-2026'


def get_db():
    return DBSession()


def require_role(role):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if 'role' not in session or session['role'] != role:
                return jsonify({'error': 'Доступ запрещён'}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


def calc_avg_service_time(db, queue_id):
    items = db.query(QueueItem).filter(
        QueueItem.queue_id == queue_id,
        QueueItem.service_start_at.isnot(None),
        QueueItem.service_end_at.isnot(None)
    ).all()
    if not items:
        return None
    total = sum((i.service_end_at - i.service_start_at).total_seconds() for i in items)
    return total / len(items)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/teacher')
def teacher_page():
    if session.get('role') != 'teacher':
        return redirect(url_for('index'))
    return render_template('teacher.html')


@app.route('/student')
def student_page():
    if session.get('role') != 'student':
        return redirect(url_for('index'))
    return render_template('student.html')


@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    isu_id = data.get('isu_id', '').strip()
    role = data.get('role', '').strip()
    if not isu_id or role not in ('teacher', 'student'):
        return jsonify({'error': 'Введите ISU ID и выберите роль'}), 400
    session['isu_id'] = isu_id
    session['role'] = role
    return jsonify({'ok': True, 'redirect': f'/{role}'})


@app.route('/api/logout', methods=['POST'])
def api_logout():
    session.clear()
    return jsonify({'ok': True})


@app.route('/api/queue/start', methods=['POST'])
@require_role('teacher')
def api_queue_start():
    data = request.get_json()
    discipline = data.get('discipline_name', '').strip()
    work = data.get('work_name', '').strip()
    if not discipline or not work:
        return jsonify({'error': 'Укажите название дисциплины и работы'}), 400

    db = get_db()
    try:
        active = db.query(Queue).filter(Queue.is_active == True).first()
        if active:
            return jsonify({'error': 'Уже существует активная очередь. Завершите её перед созданием новой.'}), 400

        q = Queue(discipline_name=discipline, work_name=work, is_active=True, paused=False)
        db.add(q)
        db.commit()
        return jsonify({'ok': True, 'queue_id': q.id})
    finally:
        db.close()


@app.route('/api/queue/pause', methods=['POST'])
@require_role('teacher')
def api_queue_pause():
    db = get_db()
    try:
        q = db.query(Queue).filter(Queue.is_active == True).first()
        if not q:
            return jsonify({'error': 'Нет активной очереди'}), 400
        q.paused = not q.paused
        db.commit()
        return jsonify({'ok': True, 'paused': q.paused})
    finally:
        db.close()


@app.route('/api/queue/next', methods=['POST'])
@require_role('teacher')
def api_queue_next():
    db = get_db()
    try:
        q = db.query(Queue).filter(Queue.is_active == True).first()
        if not q:
            return jsonify({'error': 'Нет активной очереди'}), 400
        if q.paused:
            return jsonify({'error': 'Очередь на паузе. Возобновите обслуживание.'}), 400

        current = db.query(QueueItem).filter(
            QueueItem.queue_id == q.id,
            QueueItem.status.in_(['called', 'servicing'])
        ).first()
        if current:
            current.status = 'done'
            current.service_end_at = datetime.now(timezone.utc)

        next_student = db.query(QueueItem).filter(
            QueueItem.queue_id == q.id,
            QueueItem.status == 'waiting'
        ).order_by(QueueItem.position).first()

        if not next_student:
            db.commit()
            return jsonify({'ok': True, 'message': 'Очередь пуста', 'student': None})

        next_student.status = 'called'
        next_student.service_start_at = datetime.now(timezone.utc)
        db.commit()
        return jsonify({
            'ok': True,
            'student': {
                'isu_id': next_student.student_isu_id,
                'position': next_student.position,
                'service_start_at': next_student.service_start_at.isoformat()
            }
        })
    finally:
        db.close()


@app.route('/api/queue/finish', methods=['POST'])
@require_role('teacher')
def api_queue_finish():
    db = get_db()
    try:
        q = db.query(Queue).filter(Queue.is_active == True).first()
        if not q:
            return jsonify({'error': 'Нет активной очереди'}), 400

        current = db.query(QueueItem).filter(
            QueueItem.queue_id == q.id,
            QueueItem.status.in_(['called', 'servicing'])
        ).first()
        if current:
            current.status = 'done'
            current.service_end_at = datetime.now(timezone.utc)

        q.is_active = False
        q.finished_at = datetime.now(timezone.utc)
        db.commit()
        return jsonify({'ok': True})
    finally:
        db.close()


@app.route('/api/queue/status', methods=['GET'])
def api_queue_status():
    db = get_db()
    try:
        q = db.query(Queue).filter(Queue.is_active == True).first()
        if not q:
            return jsonify({'active': False})

        items = db.query(QueueItem).filter(QueueItem.queue_id == q.id).order_by(QueueItem.position).all()

        waiting_count = sum(1 for i in items if i.status == 'waiting')
        done_count = sum(1 for i in items if i.status == 'done')
        avg_time = calc_avg_service_time(db, q.id)

        current_student = None
        for i in items:
            if i.status in ('called', 'servicing'):
                current_student = {
                    'isu_id': i.student_isu_id,
                    'position': i.position,
                    'service_start_at': i.service_start_at.isoformat() if i.service_start_at else None
                }
                break

        items_data = []
        for i in items:
            items_data.append({
                'position': i.position,
                'isu_id': i.student_isu_id,
                'status': i.status,
                'service_start_at': i.service_start_at.isoformat() if i.service_start_at else None,
                'service_end_at': i.service_end_at.isoformat() if i.service_end_at else None
            })

        not_done = sum(1 for i in items if i.status in ('waiting', 'called', 'servicing'))
        est_remaining = round(not_done * avg_time / 60, 1) if avg_time else None

        return jsonify({
            'active': True,
            'queue': {
                'id': q.id,
                'discipline_name': q.discipline_name,
                'work_name': q.work_name,
                'paused': q.paused,
                'created_at': q.created_at.isoformat()
            },
            'items': items_data,
            'stats': {
                'total': len(items),
                'waiting': waiting_count,
                'done': done_count,
                'avg_service_time_sec': round(avg_time, 1) if avg_time else None,
                'est_remaining_min': est_remaining
            },
            'current_student': current_student
        })
    finally:
        db.close()


@app.route('/api/queue/enqueue', methods=['POST'])
@require_role('student')
def api_queue_enqueue():
    db = get_db()
    try:
        q = db.query(Queue).filter(Queue.is_active == True).first()
        if not q:
            return jsonify({'error': 'Очередь не запущена'}), 400

        isu_id = session.get('isu_id')
        existing = db.query(QueueItem).filter(
            QueueItem.queue_id == q.id,
            QueueItem.student_isu_id == isu_id
        ).first()
        if existing:
            return jsonify({
                'error': 'Вы уже записаны в эту очередь',
                'status': existing.status,
                'position': existing.position
            }), 400

        max_pos = db.query(QueueItem).filter(QueueItem.queue_id == q.id).count()
        item = QueueItem(
            queue_id=q.id,
            student_isu_id=isu_id,
            position=max_pos + 1,
            status='waiting'
        )
        db.add(item)
        db.commit()

        avg_time = calc_avg_service_time(db, q.id)
        wait_items = db.query(QueueItem).filter(
            QueueItem.queue_id == q.id,
            QueueItem.status.in_(['waiting', 'called', 'servicing']),
            QueueItem.position < item.position
        ).count()
        est_wait = round((wait_items + 1) * avg_time / 60, 1) if avg_time else None

        return jsonify({
            'ok': True,
            'position': item.position,
            'est_wait_min': est_wait
        })
    finally:
        db.close()


@app.route('/api/queue/my_status', methods=['GET'])
@require_role('student')
def api_my_status():
    db = get_db()
    try:
        q = db.query(Queue).filter(Queue.is_active == True).first()
        if not q:
            return jsonify({'active': False, 'message': 'Нет активной очереди'})

        isu_id = session.get('isu_id')
        item = db.query(QueueItem).filter(
            QueueItem.queue_id == q.id,
            QueueItem.student_isu_id == isu_id
        ).first()

        if not item:
            return jsonify({
                'active': True,
                'enrolled': False,
                'queue': {
                    'discipline_name': q.discipline_name,
                    'work_name': q.work_name,
                    'paused': q.paused
                }
            })

        people_ahead = db.query(QueueItem).filter(
            QueueItem.queue_id == q.id,
            QueueItem.status == 'waiting',
            QueueItem.position < item.position
        ).count()

        avg_time = calc_avg_service_time(db, q.id)
        est_wait = round(people_ahead * avg_time / 60, 1) if avg_time and item.status == 'waiting' else None

        total_waiting = db.query(QueueItem).filter(
            QueueItem.queue_id == q.id,
            QueueItem.status == 'waiting'
        ).count()
        total_in_queue = db.query(QueueItem).filter(QueueItem.queue_id == q.id).count()
        done_count = db.query(QueueItem).filter(
            QueueItem.queue_id == q.id,
            QueueItem.status == 'done'
        ).count()

        return jsonify({
            'active': True,
            'enrolled': True,
            'queue': {
                'discipline_name': q.discipline_name,
                'work_name': q.work_name,
                'paused': q.paused
            },
            'my': {
                'position': item.position,
                'status': item.status,
                'people_ahead': people_ahead,
                'est_wait_min': est_wait
            },
            'stats': {
                'total': total_in_queue,
                'waiting': total_waiting,
                'done': done_count,
                'avg_service_time_sec': round(avg_time, 1) if avg_time else None
            }
        })
    finally:
        db.close()


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=False)
