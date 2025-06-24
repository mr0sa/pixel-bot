import cv2

# CAP_DSHOW evita um bug antigo no backend padrão do Windows
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

# peça explicitamente 1280x720 ou 1920x1080
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

# em alguns drivers você também precisa escolher o FOURCC MJPG/YUYV
fourcc = cv2.VideoWriter_fourcc(*'MJPG')
cap.set(cv2.CAP_PROP_FOURCC, fourcc)

print("W:", cap.get(cv2.CAP_PROP_FRAME_WIDTH),
      "H:", cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

while True:
    ok, frame = cap.read()
    if not ok:
        break
    cv2.imshow("OBS feed", frame)
    if cv2.waitKey(1) == 27:   # ESC
        break

cap.release()
cv2.destroyAllWindows()
