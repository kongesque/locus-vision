import sqlite3
import os
import json

DB_PATH = 'instance/tasks.db'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    # Ensure instance directory exists
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            name TEXT,
            filename TEXT,
            video_path TEXT,
            frame_path TEXT,
            frame_width INTEGER,
            frame_height INTEGER,
            points TEXT, 
            color TEXT,
            process_time REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Define columns to add: (column_name, column_definition)
    columns_to_add = [
        ('name', 'TEXT'),
        ('process_time', 'REAL'),
        ('status', 'TEXT DEFAULT "pending"'),
        ('target_class', 'INTEGER DEFAULT 19'),
        ('confidence', 'INTEGER DEFAULT 35'),
        ('detection_data', 'TEXT'),
        ('progress', 'INTEGER DEFAULT 0'),
        ('zones', 'TEXT'),
        ('model', 'TEXT DEFAULT "yolo11n.pt"'),
        ('tracker_config', 'TEXT'),
        ('source_type', 'TEXT DEFAULT "file"'),
        ('stream_url', 'TEXT'),
        ('dwell_data', 'TEXT'),
        ('line_crossing_data', 'TEXT'),
        ('heatmap_data', 'TEXT')
    ]

    for col_name, col_def in columns_to_add:
        try:
            conn.execute(f'ALTER TABLE jobs ADD COLUMN {col_name} {col_def}')
        except sqlite3.OperationalError:
            # Column likely already exists
            pass
            
    conn.commit()
    conn.close()

def create_job(task_id, filename, video_path):
    conn = get_db()
    # Default name to filename, status to pending, confidence to 35
    # Initialize with empty zones array (zones replaces points/color/target_class per zone)
    conn.execute(
        'INSERT INTO jobs (id, name, filename, video_path, points, color, status, target_class, confidence, zones) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (task_id, filename, filename, video_path, '[]', '[5, 189, 251]', 'pending', 19, 40, '[]')
    )
    conn.commit()
    conn.close()

def get_job(task_id):
    conn = get_db()
    job = conn.execute('SELECT * FROM jobs WHERE id = ?', (task_id,)).fetchone()
    conn.close()
    if job:
        # Convert Row to dict for easier manipulation if needed, handling JSON fields
        job_dict = dict(job)
        try:
            job_dict['points'] = json.loads(job_dict['points'])
        except (ValueError, TypeError):
            job_dict['points'] = []
             
        try:
             job_dict['color'] = json.loads(job_dict['color'])
        except (ValueError, TypeError):
             job_dict['color'] = [5, 189, 251]
             
        try:
             job_dict['detection_data'] = json.loads(job_dict['detection_data']) if job_dict['detection_data'] else []
        except (ValueError, TypeError):
             job_dict['detection_data'] = []

        try:
            job_dict['zones'] = json.loads(job_dict['zones']) if job_dict.get('zones') else []
        except (ValueError, TypeError):
            job_dict['zones'] = []
        
        # Parse dwell_data JSON
        try:
            job_dict['dwell_data'] = json.loads(job_dict['dwell_data']) if job_dict.get('dwell_data') else []
        except (ValueError, TypeError):
            job_dict['dwell_data'] = []
        
        # Parse line_crossing_data JSON
        try:
            job_dict['line_crossing_data'] = json.loads(job_dict['line_crossing_data']) if job_dict.get('line_crossing_data') else {}
        except (ValueError, TypeError):
            job_dict['line_crossing_data'] = {}
        
        # Parse heatmap_data JSON (2D array for activity visualization)
        try:
            job_dict['heatmap_data'] = json.loads(job_dict['heatmap_data']) if job_dict.get('heatmap_data') else None
        except (ValueError, TypeError):
            job_dict['heatmap_data'] = None
             
        # Ensure target_class is present (for old records)
        if 'target_class' not in job_dict or job_dict['target_class'] is None:
            job_dict['target_class'] = 19
            
        if 'confidence' not in job_dict or job_dict['confidence'] is None:
            job_dict['confidence'] = 35

        if 'model' not in job_dict or job_dict['model'] is None:
            job_dict['model'] = 'yolo11n.pt'

        # Parse tracker_config JSON (ByteTrack settings)
        default_tracker_config = {
            'track_high_thresh': 0.45,
            'track_low_thresh': 0.1,
            'match_thresh': 0.8,
            'track_buffer': 30
        }
        try:
            job_dict['tracker_config'] = json.loads(job_dict['tracker_config']) if job_dict.get('tracker_config') else default_tracker_config
        except (ValueError, TypeError):
            job_dict['tracker_config'] = default_tracker_config

        # Ensure source_type is present (for old records)
        if 'source_type' not in job_dict or job_dict['source_type'] is None:
            job_dict['source_type'] = 'file'
             
        return job_dict
    return None

def get_all_jobs(status=None):
    conn = get_db()
    if status:
        jobs = conn.execute('SELECT * FROM jobs WHERE status = ? ORDER BY created_at DESC', (status,)).fetchall()
    else:
        jobs = conn.execute('SELECT * FROM jobs ORDER BY created_at DESC').fetchall()
    conn.close()
    return [dict(job) for job in jobs]

def delete_job(task_id):
    conn = get_db()
    conn.execute('DELETE FROM jobs WHERE id = ?', (task_id,))
    conn.commit()
    conn.close()

def clear_all_jobs():
    """Delete all jobs from the database."""
    conn = get_db()
    conn.execute('DELETE FROM jobs')
    conn.commit()
    conn.close()

def update_job(task_id, **kwargs):
    conn = get_db()
    
    # Pre-process JSON fields
    if 'points' in kwargs:
        kwargs['points'] = json.dumps(kwargs['points'])
    if 'color' in kwargs:
        kwargs['color'] = json.dumps(kwargs['color'])
    if 'detection_data' in kwargs:
        kwargs['detection_data'] = json.dumps(kwargs['detection_data'])
    if 'zones' in kwargs:
        kwargs['zones'] = json.dumps(kwargs['zones'])
    if 'tracker_config' in kwargs:
        kwargs['tracker_config'] = json.dumps(kwargs['tracker_config'])
    if 'dwell_data' in kwargs:
        kwargs['dwell_data'] = json.dumps(kwargs['dwell_data'])
    if 'line_crossing_data' in kwargs:
        kwargs['line_crossing_data'] = json.dumps(kwargs['line_crossing_data'])
    if 'heatmap_data' in kwargs:
        kwargs['heatmap_data'] = json.dumps(kwargs['heatmap_data'])

    columns = ', '.join(f"{key} = ?" for key in kwargs.keys())
    values = list(kwargs.values())
    values.append(task_id)
    
    conn.execute(f'UPDATE jobs SET {columns} WHERE id = ?', values)
    conn.commit()
    conn.close()

