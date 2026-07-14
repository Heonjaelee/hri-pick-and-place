// GestureClassifier.cs
// Quest Pro 손 트래킹(OVRSkeleton)에서 6개 제스처를 분류
// 확정 제스처: Open_Palm, Pointing_Up, Closed_Fist, Victory, Pinch, Thumb_Down
//
// 사용법: 씬에 OVRHand + OVRSkeleton이 붙은 오른손 오브젝트에 추가

using UnityEngine;
using System.Collections.Generic;

public class GestureClassifier : MonoBehaviour
{
    public OVRHand hand;
    public OVRSkeleton skeleton;

    public string CurrentGesture { get; private set; } = "Open_Palm";
    public float CurrentConfidence { get; private set; } = 0f;

    // 손가락 굽힘 판정 임계값 (관절 각도 기반)
    const float CURL_THRESHOLD = 0.6f;

    void Update()
    {
        if (hand == null || !hand.IsTracked || skeleton == null ||
            skeleton.Bones == null || skeleton.Bones.Count == 0)
        {
            CurrentGesture = "Open_Palm";
            CurrentConfidence = 0f;
            return;
        }

        float trackingConf =
            hand.HandConfidence == OVRHand.TrackingConfidence.High ? 1.0f : 0.5f;

        // 1) Pinch: SDK 내장 판정 (엄지+검지 맞닿음) — 홈 복귀
        if (hand.GetFingerIsPinching(OVRHand.HandFinger.Index) &&
            hand.GetFingerPinchStrength(OVRHand.HandFinger.Index) > 0.85f)
        {
            Set("Pinch", trackingConf * hand.GetFingerPinchStrength(OVRHand.HandFinger.Index));
            return;
        }

        // 손가락별 굽힘 정도 계산
        float thumbCurl  = FingerCurl(OVRSkeleton.BoneId.Hand_Thumb1,
                                      OVRSkeleton.BoneId.Hand_Thumb2,
                                      OVRSkeleton.BoneId.Hand_Thumb3);
        float indexCurl  = FingerCurl(OVRSkeleton.BoneId.Hand_Index1,
                                      OVRSkeleton.BoneId.Hand_Index2,
                                      OVRSkeleton.BoneId.Hand_Index3);
        float middleCurl = FingerCurl(OVRSkeleton.BoneId.Hand_Middle1,
                                      OVRSkeleton.BoneId.Hand_Middle2,
                                      OVRSkeleton.BoneId.Hand_Middle3);
        float ringCurl   = FingerCurl(OVRSkeleton.BoneId.Hand_Ring1,
                                      OVRSkeleton.BoneId.Hand_Ring2,
                                      OVRSkeleton.BoneId.Hand_Ring3);
        float pinkyCurl  = FingerCurl(OVRSkeleton.BoneId.Hand_Pinky1,
                                      OVRSkeleton.BoneId.Hand_Pinky2,
                                      OVRSkeleton.BoneId.Hand_Pinky3);

        bool indexOpen  = indexCurl  < CURL_THRESHOLD;
        bool middleOpen = middleCurl < CURL_THRESHOLD;
        bool ringOpen   = ringCurl   < CURL_THRESHOLD;
        bool pinkyOpen  = pinkyCurl  < CURL_THRESHOLD;
        bool thumbOpen  = thumbCurl  < CURL_THRESHOLD;

        int openCount = (indexOpen?1:0) + (middleOpen?1:0) +
                        (ringOpen?1:0)  + (pinkyOpen?1:0);

        // 엄지 방향 (Thumb_Down 판정용): 엄지 끝이 손목보다 아래인가
        Vector3 wrist    = BonePos(OVRSkeleton.BoneId.Hand_WristRoot);
        Vector3 thumbTip = BonePos(OVRSkeleton.BoneId.Hand_ThumbTip);
        bool thumbBelow  = (thumbTip.y < wrist.y - 0.03f);

        // 2) Thumb_Down: 네 손가락 모두 굽힘 + 엄지만 펴짐 + 엄지가 아래 — 즉시 정지
        if (openCount == 0 && thumbOpen && thumbBelow)
        {
            Set("Thumb_Down", trackingConf * 0.95f);
            return;
        }

        // 3) Closed_Fist: 모든 손가락 굽힘 — 파지 / 들고 이동
        if (openCount == 0 && !thumbOpen)
        {
            Set("Closed_Fist", trackingConf * Mathf.Min(indexCurl, middleCurl));
            return;
        }

        // 4) Pointing_Up: 검지만 펴짐 — 이동
        if (indexOpen && !middleOpen && !ringOpen && !pinkyOpen)
        {
            Set("Pointing_Up", trackingConf * (1f - indexCurl));
            return;
        }

        // 5) Victory: 검지+중지만 펴짐 — 내려놓기
        if (indexOpen && middleOpen && !ringOpen && !pinkyOpen)
        {
            Set("Victory", trackingConf * (1f - Mathf.Max(indexCurl, middleCurl)));
            return;
        }

        // 6) Open_Palm: 네 손가락 모두 펴짐 — 대기
        if (openCount == 4)
        {
            Set("Open_Palm", trackingConf * 0.9f);
            return;
        }

        // 애매한 손 모양은 낮은 신뢰도의 Open_Palm으로
        Set("Open_Palm", 0.3f);
    }

    void Set(string g, float c)
    {
        CurrentGesture = g;
        CurrentConfidence = Mathf.Clamp01(c);
    }

    Vector3 BonePos(OVRSkeleton.BoneId id)
    {
        foreach (var b in skeleton.Bones)
            if (b.Id == id) return b.Transform.position;
        return Vector3.zero;
    }

    // 세 관절이 이루는 각도로 굽힘 정도 산출 (0=완전히 펴짐, 1=완전히 굽힘)
    float FingerCurl(OVRSkeleton.BoneId b1, OVRSkeleton.BoneId b2, OVRSkeleton.BoneId b3)
    {
        Vector3 p1 = BonePos(b1), p2 = BonePos(b2), p3 = BonePos(b3);
        Vector3 v1 = (p2 - p1).normalized;
        Vector3 v2 = (p3 - p2).normalized;
        float angle = Vector3.Angle(v1, v2);          // 0(펴짐) ~ 180
        return Mathf.Clamp01(angle / 120f);
    }
}
