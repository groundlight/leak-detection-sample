import os
import sys
import yaml
import logging
from pydantic import Field, BaseModel

logger = logging.getLogger(__name__)


class LeakDetectorIDs(BaseModel):
    detect_leaks: str = Field(..., description="Detector ID of the binary leak detector")
    count_leaks: str = Field(..., description="Detector ID of the counting leak counter")
    classify_leaks: str = Field(..., description="Detector ID of the multi-class leak classifier")


class Config(BaseModel):
    endpoint: str = Field(None, description="Edge Endpoint URL, default None")
    leak_detector_ids: LeakDetectorIDs = Field(..., description="ML Detector Configs")
    enable_motion_detection: bool = Field(False, description="Enable motion detection")
    motion_detection_threshold: float = Field(0.1, description="Motion detection threshold")


CONFIG_FILE_PATH = "./configs/config.yaml"
CAMERA_CONFIG_FILE_PATH = "./configs/camera.yaml"

# Load configuration
try:
    with open(CONFIG_FILE_PATH, "r") as file:
        config_dict = yaml.safe_load(file)
        config = Config(**config_dict)

    with open(CAMERA_CONFIG_FILE_PATH, "r") as file:
        camera_config_dict = yaml.safe_load(file)

    logger.info("Configuration loaded successfully!")
except Exception as e:
    logger.error(f"Error loading configuration: {e}", exc_info=True)
    sys.exit(1)
