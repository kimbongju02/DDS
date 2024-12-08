from django.shortcuts import render

from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import detect

import time
import os
import json
import numpy as np
import queue
import cv2
import base64

folder_path = os.path.join(settings.MEDIA_ROOT, 'videos', 'received_frame.jpg')
frame_queue = queue.Queue(maxsize=10)  # 프레임 저장 큐
last_frame = None  # 마지막 프레임 저장

def index(request):
    return render(request, '.\\pybo\\main.html')

@csrf_exempt
def set_folder(request):
    if request.method == 'POST':
        image = request.FILES.get('image')
        if not image:
            return JsonResponse({'status': 'error', 'message': 'No image uploaded'}, status=400)
        return JsonResponse({'status': 'success', 'message': f'Image {image.name} uploaded successfully'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=405)

def image_stream_generator():
    global last_frame
    while True:
        if not frame_queue.empty():
            last_frame = frame_queue.get().copy()
        if last_frame is not None:
            _, encoded_image = cv2.imencode('.jpg', last_frame)
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + encoded_image.tobytes() + b'\r\n')
        else:
            time.sleep(0.1)

def get_image(request):
    return StreamingHttpResponse(image_stream_generator(), content_type='multipart/x-mixed-replace; boundary=frame')

def get_yolo_image(request):
    global last_frame
    if last_frame is not None:
        try:
            yolo_result = detect.run(matrix=last_frame)
            sent_txt = "null"
            if 'image_matrix' in yolo_result:
                _, encoded_image = cv2.imencode('.jpg', yolo_result['image_matrix'])
                
                # 이미지 데이터를 Base64로 인코딩
                base64_image = base64.b64encode(encoded_image.tobytes()).decode('utf-8')
                
                for i in yolo_result['detections']:
                    if "fire" or "person" in i['label']:
                        if float(i['confidence_str']) >= 0.3:
                            sent_txt = i['label']
                            
                boundary = "frame_boundary"
                response_content = (
                    f"--{boundary}\r\n"
                    f"Content-Type: image/jpeg\r\n\r\n"
                    + base64_image  # Base64 인코딩된 이미지
                    + f"\r\n--{boundary}\r\n"
                    f"Content-Type: text/plain\r\n\r\n"
                    f"{sent_txt}\r\n"
                    f"--{boundary}--\r\n"
                )
                
                return HttpResponse(
                    response_content,
                    content_type=f"multipart/mixed; boundary={boundary}"
                )
            else:
                return JsonResponse({'status': 'error', 'message': 'YOLO 결과에 이미지가 없습니다.'}, status=500)
        except SystemExit as e:
            print(f"SystemExit 발생: {e}")
            return JsonResponse({'status': 'error', 'message': 'YOLO 실행 중 오류가 발생했습니다.'}, status=500)
    else:
        time.sleep(0.1)
        return JsonResponse({'status': 'error', 'message': '프레임 큐가 비어 있습니다.'}, status=404)

@csrf_exempt
def receive_image(request):
    if request.method == 'POST':
        if frame_queue.full():
            try:
                frame_queue.get_nowait()
            except queue.Empty:
                pass
        image_data = np.frombuffer(request.body, dtype=np.uint8)
        image = cv2.imdecode(image_data, cv2.IMREAD_COLOR)
        frame_queue.put(image)

        return JsonResponse({'status': 'success', 'message': 'Frame received successfully'})

    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)