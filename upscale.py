import cv2
from cv2 import dnn_superres
from io import BytesIO
import numpy as np

save = None
def upscale(input_bytes: BytesIO, output_bytes: BytesIO, model_path: str = 'EDSR_x2.pb') -> None:
    global save
    if save is None:
        save = dnn_superres.DnnSuperResImpl_create()
        save.readModel(model_path)
        save.setModel("edsr", 2)
    input_bytes.seek(0)
    nparr = np.frombuffer(input_bytes.read(), np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Не удалось декодировать изображение")
    result = save.upsample(image)
    _, buffer = cv2.imencode('.png', result, [cv2.IMWRITE_PNG_COMPRESSION, 0])
    output_bytes.write(buffer.tobytes())
    output_bytes.seek(0)
