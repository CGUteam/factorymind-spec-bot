# Robot Inspection Module

## Environment

Python 3.10+

## Dependencies

### LeRobot

```bash
git clone https://github.com/huggingface/lerobot.git

cd lerobot

pip install -e .
```

### RealSense

Install Intel RealSense SDK and Python bindings:

```bash
sudo apt install librealsense2-utils
pip install pyrealsense2
```

### Gemini

```bash
pip install google-genai
```

Set API key:

```bash
export GEMINI_API_KEY=YOUR_API_KEY
```

## Run API Server

```bash
uvicorn factorymind-spec-bot:app --host 0.0.0.0 --port 8000
```

## Workflow

1. Receive inspection task JSON from FactoryMind.
2. Save the received JSON as `received_task.json`.
3. Execute the LeRobot `scale` policy to move the product onto the electronic scale.
4. Capture the test image using the RealSense D435 camera.
5. Send three inputs to Gemini:
   - the received inspection task JSON
   - the standard reference image
   - the captured test image
6. Gemini compares the task requirements, standard image, and test image, then returns an inspection result JSON.
7. Parse and normalize the Gemini JSON result.
8. If `pass = true`, execute the PASS placement policy.
9. If `pass = false`, execute the FAIL placement policy.
10. Return the final result JSON to the requester.
```
```

