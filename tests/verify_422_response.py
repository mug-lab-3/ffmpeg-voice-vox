import requests
import json

def test_validation_error_response():
    url = "http://127.0.0.1:3000/api/config/synthesis"
    payload = {"speed_scale": 9.9} # Invalid value (max 1.5)

    print(f"Sending invalid request to {url}...")
    response = requests.post(url, json=payload)

    print(f"Status Code: {response.status_code}")
    data = response.json()
    print("Response Data:")
    print(json.dumps(data, indent=2))

    assert response.status_code == 422
    assert data["status"] == "error"
    assert data["error_code"] == "INVALID_ARGUMENT"
    assert "config" in data
    assert "speaker_id" in data["config"]
    print("\nVerification Successful: 422 response contains the current valid config.")

if __name__ == "__main__":
    try:
        test_validation_error_response()
    except Exception as e:
        print(f"Test Failed: {e}")
