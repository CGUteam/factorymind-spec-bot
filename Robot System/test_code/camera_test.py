import pyrealsense2 as rs
import numpy as np
import cv2

pipeline = rs.pipeline()
config = rs.config()

config.enable_stream(
    rs.stream.color,
    1920,
    1080,
    rs.format.bgr8,
    8
)

pipeline.start(config)

try:
    for _ in range(30):
        frames = pipeline.wait_for_frames()

    color_frame = frames.get_color_frame()

    if not color_frame:
        raise RuntimeError("沒有讀到 color frame")

    image = np.asanyarray(color_frame.get_data())

    cv2.imwrite("realsense_color.jpg", image)

    print("saved realsense_color.jpg")
    print("shape:", image.shape)

finally:
    pipeline.stop()
