from io import BytesIO
from flask import Flask, jsonify, request, send_from_directory
from flask.views import MethodView
from celery.result import AsyncResult
from celery import Celery
import uuid
import os
from upscale import upscale

app_name = 'app'
app = Flask(app_name)
app.config['UPLOAD_FOLDER'] = 'files'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


celery_app = Celery(
    app.import_name,
    broker='redis://redis:6379/0',
    backend='redis://redis:6379/1'
)
celery_app.conf.update(app.config)

class ContextTask(celery_app.Task):
    def __call__(self, *args, **kwargs):
        with app.app_context():
            return self.run(*args, **kwargs)

celery_app.Task = ContextTask


@celery_app.task()
def process_image(image_bytes, output_name):
    try:
        image_io = BytesIO(image_bytes)
        result_io = BytesIO()
        upscale(image_io, result_io)
        result_io.seek(0)

        output_filename = f"{output_name}_HD.png"
        output_path = os.path.join('files', output_filename)

        with open(output_path, 'wb') as f:
            f.write(result_io.getvalue())

        return output_filename
    finally:
        result_io.close()
        image_io.close()


ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'bmp', 'tiff'}

@app.route('/processed/<filename>')
def processed_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

class Comparison(MethodView):
    def get(self, task_id):
        task = AsyncResult(task_id, app=celery_app)
        if task.state == 'PENDING':
            return jsonify({'status': 'pending'})
        elif task.state == 'SUCCESS':
            return jsonify({
                'status': 'completed',
                'processed_file': str(task.result)
            })
        elif task.state == 'FAILURE':
            return jsonify({'status': 'failed'})
        return jsonify({'status': task.state})

    def post(self):
        if 'image' not in request.files:
            return jsonify({'error': 'No image provided'}), 400

        image = request.files['image']
        if image.filename == '':
            return jsonify({'error': 'No image selected'}), 400


        filename = image.filename.lower()
        if '.' not in filename:
            return jsonify({'error': 'Invalid filename'}), 400
        file_ext = filename.rsplit('.', 1)[1].lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            return jsonify({'error': f'Allowed: {", ".join(ALLOWED_EXTENSIONS)}'}), 400

        image_bytes = image.read()
        name = str(uuid.uuid4())
        task = celery_app.send_task('celery_app.process_image', args=[image_bytes, name])
        return jsonify({'task_id': task.id}), 202

upscale_view = Comparison.as_view('upscale_api')
app.add_url_rule('/upscale', view_func=upscale_view, methods=['POST'])
app.add_url_rule('/tasks/<task_id>', view_func=upscale_view, methods=['GET'])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
