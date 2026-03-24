import os
import io
import logging
import magic
from flask import Flask, jsonify, request, send_file, redirect, url_for, render_template
from flask.views import MethodView
from celery.result import AsyncResult
from tasks import app_celery, upscale_task

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask('app')

PORT = int(os.getenv('PORT', 5001))
HOST = os.getenv('HOST', '0.0.0.0')
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
MAX_CONTENT_LENGTH = 50 * 1024 * 1024

app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

ALLOWED_MIME_TYPES = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}
ALLOWED_EXTENSIONS = {'jpg', 'png', 'jpeg', 'gif', 'webp'}


def validate_model_files():
    """Проверяет наличие модели при запуске"""
    model_path = "models/EDSR_x2.pb"
    if not os.path.exists(model_path):
        logger.error(f"Model file not found: {model_path}")
        raise FileNotFoundError(f"Required model file not found: {model_path}")
    logger.info(f"Model file validated: {model_path}")


def allowed_file(filename: str) -> bool:
    """Проверяет расширение файла"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def validate_mime_type(file_bytes: bytes) -> tuple[bool, str]:
    """Проверяет настоящий тип загруженного файла"""
    try:
        mime = magic.Magic(mime=True)
        mime_type = mime.from_buffer(file_bytes)
        return mime_type in ALLOWED_MIME_TYPES, mime_type
    except Exception as e:
        logger.warning(f"Failed to detect MIME type: {e}")
        return False, "unknown"


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/result/<task_id>')
def result(task_id):
    task = AsyncResult(task_id, app=app_celery)
    return render_template('result.html', task_id=task_id, task=task)


class Processing(MethodView):
    def get(self, task_id):
        task = AsyncResult(task_id, app=app_celery)
        if task.state == 'SUCCESS':
            img_bytes = task.result
            return send_file(
                io.BytesIO(img_bytes),
                mimetype='image/png',
                as_attachment=False,
                download_name='upscaled.png'
            )
        return jsonify({'status': task.state})

    def post(self):
        use_edsr = request.form.get('model') == 'edsr'
        
        if 'image' not in request.files:
            logger.warning("No image provided in request")
            return jsonify({'error': 'No image provided'}), 400
        
        file = request.files['image']
        file_name = file.filename
        
        if file_name == '' or '.' not in file_name:
            logger.warning(f"Invalid filename: {file_name}")
            return jsonify({'error': 'No image provided'}), 400
        
        if not allowed_file(file_name):
            logger.warning(f"Disallowed file extension: {file_name}")
            return jsonify({'error': f'Allowed: {", ".join(ALLOWED_EXTENSIONS)}'}), 400
        
        file_bytes = file.read()
        
        is_valid_mime, mime_type = validate_mime_type(file_bytes)
        if not is_valid_mime:
            logger.warning(f"Disallowed MIME type: {mime_type} for file: {file_name}")
            return jsonify({'error': f'Invalid file type. Allowed: {", ".join(ALLOWED_MIME_TYPES)}'}), 400
        
        logger.info(f"Processing image: {file_name} (MIME: {mime_type}, EDSR: {use_edsr})")
        
        task = upscale_task.delay(image_bytes=file_bytes, use_edsr=use_edsr)
        return redirect(url_for('result', task_id=task.id))


app.add_url_rule('/upscale/<task_id>', view_func=Processing.as_view('task_get'), methods=['GET'])
app.add_url_rule('/upscale', view_func=Processing.as_view('upscale'), methods=['POST'])


if __name__ == '__main__':
    validate_model_files()
    
    logger.info(f"Starting Flask app on {HOST}:{PORT} (debug={DEBUG})")
    app.run(
        debug=DEBUG,
        host=HOST,
        port=PORT,
        threaded=True
    )
