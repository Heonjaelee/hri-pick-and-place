// QuestSender.cs
// Quest Pro의 화면상 gaze 좌표 + 제스처를 PC로 WebSocket 전송 (30Hz)
// 화면에 표시 중인 카메라 영상(RawImage) 기준 정규화 좌표(0~1)를 보냄
//
// 의존성: NativeWebSocket (https://github.com/endel/NativeWebSocket)
// 씬 구성: OVREyeGaze 컴포넌트, 카메라 영상이 표시되는 RawImage(videoScreen)

using UnityEngine;
using UnityEngine.UI;
using NativeWebSocket;

public class QuestSender : MonoBehaviour
{
    [Header("연결 설정")]
    public string pcAddress = "ws://192.168.0.10:8766";   // PC IP로 변경

    [Header("씬 참조")]
    public OVREyeGaze eyeGaze;            // 좌/우 눈 융합 gaze
    public RectTransform videoScreen;     // 카메라 영상이 표시되는 RawImage
    public GestureClassifier gesture;     // 제스처 분류기
    public RectTransform gazeCursor;      // 시선 커서 UI (선택)

    WebSocket ws;
    float sendInterval = 1f / 30f;
    float timer = 0f;

    async void Start()
    {
        ws = new WebSocket(pcAddress);
        ws.OnOpen  += () => Debug.Log("PC 연결됨");
        ws.OnError += (e) => Debug.LogWarning("WS 오류: " + e);
        await ws.Connect();
    }

    void Update()
    {
        ws?.DispatchMessageQueue();

        timer += Time.deltaTime;
        if (timer < sendInterval) return;
        timer = 0f;

        if (ws == null || ws.State != WebSocketState.Open) return;

        // 1) 시선 Ray → 영상 화면(RawImage) 평면과 교차 → 정규화 좌표
        Vector2 gazeNorm = GazeOnScreen();

        // 시선 커서 표시 (작업자 피드백)
        if (gazeCursor != null && videoScreen != null)
        {
            Rect r = videoScreen.rect;
            gazeCursor.anchoredPosition = new Vector2(
                (gazeNorm.x - 0.5f) * r.width,
                (0.5f - gazeNorm.y) * r.height);
        }

        // 2) JSON 직렬화 후 전송
        string json = JsonUtility.ToJson(new Packet
        {
            gaze_x = gazeNorm.x,
            gaze_y = gazeNorm.y,
            gesture = gesture != null ? gesture.CurrentGesture : "Open_Palm",
            confidence = gesture != null ? gesture.CurrentConfidence : 0f
        });
        ws.SendText(json);
    }

    Vector2 GazeOnScreen()
    {
        if (eyeGaze == null || videoScreen == null)
            return new Vector2(0.5f, 0.5f);

        // 시선 Ray가 영상 화면 평면과 만나는 점 계산
        Ray ray = new Ray(eyeGaze.transform.position, eyeGaze.transform.forward);
        Plane plane = new Plane(-videoScreen.forward, videoScreen.position);

        if (!plane.Raycast(ray, out float dist))
            return new Vector2(0.5f, 0.5f);

        Vector3 hit = ray.GetPoint(dist);
        Vector3 local = videoScreen.InverseTransformPoint(hit);
        Rect r = videoScreen.rect;

        // 로컬 좌표 → 0~1 정규화 (좌상단 원점, 이미지 좌표계와 일치)
        float u = Mathf.Clamp01((local.x - r.xMin) / r.width);
        float v = Mathf.Clamp01(1f - (local.y - r.yMin) / r.height);
        return new Vector2(u, v);
    }

    async void OnApplicationQuit()
    {
        if (ws != null) await ws.Close();
    }

    [System.Serializable]
    class Packet
    {
        public float gaze_x;
        public float gaze_y;
        public string gesture;
        public float confidence;
    }
}
