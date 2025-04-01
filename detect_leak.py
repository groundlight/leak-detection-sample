import sys
import cv2
import logging

from framegrab import FrameGrabber, MotionDetector
from groundlight import Groundlight

from config import config, camera_config_dict

logger = logging.getLogger(__name__)


def main():
    logger.info("Starting frame grabber")

    try:
        grabber = FrameGrabber.create_grabber(config=camera_config_dict)

        if config.enable_motion_detection:
            motion_detector = MotionDetector(pct_threshold=config.motion_detection_threshold)

    except Exception as e:
        logger.error(f"Error creating frame grabber: {e}", exc_info=True)
        sys.exit(1)

    try:
        gl = Groundlight(endpoint=config.endpoint)
        detect_leaks = gl.get_detector(id=config.leak_detector_ids.detect_leaks)
        count_leaks = gl.get_detector(id=config.leak_detector_ids.count_leaks)
        classify_leaks = gl.get_detector(id=config.leak_detector_ids.classify_leaks)
    except Exception as e:
        logger.error(f"Error connecting to groundlight services: {e}", exc_info=True)
        sys.exit(1)

    current_frame_num = 1

    while True:
        try:
            frame = grabber.grab()
            annotated_frame = frame.copy()

            if config.enable_motion_detection and not motion_detector.motion_detected(frame):
                logger.info(f"No significant motion detected in frame {current_frame_num}, skipping frame.")
                current_frame_num += 1
                continue

        except Exception as e:
            logger.warning(f"Cannot grab next frame. Possible end of file: {e}", exc_info=True)
            break

        try:
            # Send the frame to the binary leak detector to check if there are any leaks in the frame
            iq_detect_leaks = gl.submit_image_query(detector=detect_leaks, image=frame)

            if iq_detect_leaks.confidence_threshold < iq_detect_leaks.result.confidence and iq_detect_leaks.result.label == "YES":
                logger.debug(f"Leak detected with confidence: {iq_detect_leaks.result.confidence}")
                logger.debug("Sending frame to counting detector")

                # Send the frame to the count leak detector to get the ROIs of the all the leaks in the frame
                iq_count_leaks = gl.submit_image_query(detector=count_leaks, image=frame)

                if iq_count_leaks.confidence_threshold < iq_count_leaks.result.confidence:
                    logger.debug(f"Leak count detected with confidence: {iq_count_leaks.result.confidence}")

                    leak_rois = iq_count_leaks.rois

                    if leak_rois is not None:
                        for roi in leak_rois:
                            # For each detected leak, send the ROI to the classifier to classify what type of leak it is
                            # Expand the ROI to include some context around the leak, 5% of each side

                            (h, w) = frame.shape[:2]

                            top = roi.geometry.top * h
                            left = roi.geometry.left * w
                            bottom = roi.geometry.bottom * h
                            right = roi.geometry.right * w

                            # Expand the ROI by 5% on each side
                            top = int(max(0, top - 0.05 * h))
                            left = int(max(0, left - 0.05 * w))
                            bottom = int(min(h, bottom + 0.05 * h))
                            right = int(min(w, right + 0.05 * w))
                            roi_image = frame[top:bottom, left:right]

                            # Send the ROI to the classifier
                            iq_classify_leaks = gl.submit_image_query(detector=classify_leaks, image=roi_image)

                            if iq_classify_leaks.confidence_threshold < iq_classify_leaks.result.confidence:
                                logger.debug(f"Leak classified with confidence: {iq_classify_leaks.result.confidence}")
                                logger.info(f"Frame {current_frame_num}: Leak detected and classified as: {iq_classify_leaks.result.label}")

                                # Draw the bounding box and the class on the annotated frame
                                cv2.rectangle(annotated_frame, (left, top), (right, bottom), (0, 255, 0), 2)
                                cv2.putText(
                                    annotated_frame,
                                    f"Leak: {iq_classify_leaks.result.label}",
                                    (left, top - 10),
                                    cv2.FONT_HERSHEY_SIMPLEX,
                                    0.5,
                                    (0, 255, 0),
                                    2,
                                )

            # Show the frame with the detected leaks
            cv2.imshow("Frame", annotated_frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

            current_frame_num += 1
            logger.info(f"Processed frame {current_frame_num}")
        except Exception as e:
            logger.error(f"Error processing frame: {e}", exc_info=True)
            break


if __name__ == "__main__":
    main()
