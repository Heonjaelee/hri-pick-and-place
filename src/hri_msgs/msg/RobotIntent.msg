# 의도 인식 결과 -> 로봇 명령
std_msgs/Header header

# 0=IDLE 1=MOVE_TO 2=PICK 3=PLACE 4=HOME 5=ABORT
int32 action

# gaze 기반 목표 위치 (로봇 base 좌표계, 미터)
geometry_msgs/Point target_position

float32 confidence
string gesture_label
