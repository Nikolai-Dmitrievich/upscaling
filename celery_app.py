import os
from flask.views import MethodView
from upscale import upscale
from flask import Flask, jsonify, request, send_from_directory
from celery.result import AsyncResult
from celery import Celery
import uuid


app_name = 'app'
app = Flask(app_name)
app.config['UPLOAD_FOLDER'] = 'files'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
celery_app = Celery(
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
def process_image(image_path):
    name, ext = os.path.splitext(os.path.basename(image_path))
    output_filename = f"{name}_HD{ext}"
    output_path = os.path.join('files', output_filename)

    upscale(image_path, output_path)
    return output_filename

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
        else:
            return jsonify({'status': task.state})
    def post(self):
        if 'image' not in request.files:
            return jsonify({'error': 'No image provided'}), 400

        image = request.files['image']
        if image.filename == '':
            return jsonify({'error': 'No image selected'}), 400
        extension = image.filename.split('.')[-1]
        path = os.path.join(app.config['UPLOAD_FOLDER'], f'{uuid.uuid4()}.{extension}')
        image.save(path)
        task = celery_app.send_task('celery_app.process_image', args=[path])
        return jsonify({'task_id': task.id})

@app.route('/processed/<filename>')
def processed_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


upscale_view = Comparison.as_view('upscale_api')
app.add_url_rule('/upscale', view_func=upscale_view, methods=['POST'])
app.add_url_rule('/tasks/<task_id>', view_func=upscale_view, methods=['GET'])



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)