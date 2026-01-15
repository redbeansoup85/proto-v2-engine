from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.emotion_os.models.emotion import EmotionRecordRequest, EmotionRecordResponse
from core.emotion_os.core.kernel_v1 import evaluate_emotion

app = FastAPI(
    title="Emotion OS API v1.0",
    description="Emotion OS L1 Kernel v1.0 HTTP API",
    version="1.0.0",
)

# CORS 설정 (나중에 프론트에서 직접 호출 가능하게)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # 필요하면 나중에 특정 도메인으로 줄이면 됨
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/emotion/record", response_model=EmotionRecordResponse)
def record_emotion(req: EmotionRecordRequest) -> EmotionRecordResponse:
    """
    Emotion OS v1.0 공식 엔드포인트
    - 입력: EmotionRecordRequest
    - 출력: EmotionRecordResponse (커널 v1.0 결과)
    """
    return evaluate_emotion(req)
