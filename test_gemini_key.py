from google import genai

client = genai.Client(api_key="AIzaSyBL5JqtBSOAayRMJ_b-lDiBcLLWLUf0E8s")

response = client.models.generate_content(
    model="models/gemini-2.0-flash-lite",
    contents="Say hello in one word"
)

print(response.text)