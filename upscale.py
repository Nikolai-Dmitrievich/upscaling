import cv2
import numpy as np
from io import BytesIO
from cv2 import dnn_superres
import logging

logger = logging.getLogger(__name__)


def upscale(
    input_bytes: BytesIO,
    output_bytes: BytesIO,
    method: str = "opencv",
    model_path: str = "models/EDSR_x2.pb"
) -> None:
    """
    Увеличивает изображение в 2 раза
    
    Аргументы:
        input_bytes: PNG картинка (байты)
        output_bytes: Куда сохранить увеличенную картинку  
        method: "opencv" (быстро) или "edsr" (качественно)
        model_path: Путь к нейросети EDSR (только для edsr)
    
    Ошибки:
        ValueError: Не картинка или сломанная
        FileNotFoundError: Нет файла нейросети EDSR
    """
    nparr = np.frombuffer(input_bytes.getvalue(), np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Failed to decode image")

    if method == "edsr":
        super_resolution_model = dnn_superres.DnnSuperResImpl_create()
        super_resolution_model.readModel(model_path)
        super_resolution_model.setModel("edsr", 2)
        result = super_resolution_model.upsample(img)
    else:
        h, w = img.shape[:2]
        result = cv2.resize(img, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)

    _, buffer = cv2.imencode('.png', result, [cv2.IMWRITE_PNG_COMPRESSION, 0])
    output_bytes.write(buffer.tobytes())
    output_bytes.seek(0)
    
    logger.info(f"Image upscaled successfully using method: {method}")
