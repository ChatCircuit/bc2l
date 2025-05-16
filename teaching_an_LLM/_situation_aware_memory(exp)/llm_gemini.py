from google import genai
import time

client = genai.Client(api_key="AIzaSyBBMeE2Qluk-v2de60x35i3RpZjTVZtiJ4")

response = client.models.generate_content(
    model="gemini-2.0-flash", contents="tell the capital of 30 random countries"
)

print(response.usage_metadata.total_token_count)


