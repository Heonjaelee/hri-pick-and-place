// VideoReceiver.cs
// PC가 보내는 스테레오 카메라 Left RGB(JPEG)를 수신해서 화면에 표시
// 의존성: NativeWebSocket

using UnityEngine;
using UnityEngine.UI;
using NativeWebSocket;

public class VideoReceiver : MonoBehaviour
{
    public string pcAddress = "ws://192.168.0.10:8765";   // PC IP로 변경
    public RawImage videoScreen;                          // 작업자가 보는 화면

    WebSocket ws;
    Texture2D tex;
    byte[] pending = null;

    async void Start()
    {
        tex = new Texture2D(2, 2, TextureFormat.RGB24, false);
        videoScreen.texture = tex;

        ws = new WebSocket(pcAddress);
        ws.OnMessage += (bytes) => pending = bytes;   // 메인스레드에서 디코딩
        ws.OnOpen    += () => Debug.Log("영상 스트림 연결됨");
        await ws.Connect();
    }

    void Update()
    {
        ws?.DispatchMessageQueue();

        if (pending != null)
        {
            tex.LoadImage(pending);   // JPEG 디코딩
            pending = null;
        }
    }

    async void OnApplicationQuit()
    {
        if (ws != null) await ws.Close();
    }
}
