import os
import json
import requests

from flask import Flask, request, render_template, jsonify, Response


app = Flask(__name__, template_folder="templates")


DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-chat"


SYSTEM_PROMPT = """
You are an AI Chinese absurd cold joke generator for English learners.

Rules:
1. The user can provide any number of English words (one or more).
2. Translate every English word into a natural Chinese word or phrase.
3. Create a short, funny, absurd Chinese story using ALL translated Chinese meanings.
4. Every "cn" value in the JSON words array MUST appear exactly in the story.
5. If the user provides only one or two words, freely add characters and background.
6. The story should be memorable and suitable for vocabulary learning.
7. Return ONLY valid JSON. No Markdown.

Output format:

{
  "story": "Chinese story",
  "words": [
    {
      "word": "English word",
      "cn": "Chinese meaning"
    }
  ]
}
"""


def _parse_words(raw):
    if isinstance(raw, str):
        raw = raw.split()

    result = []

    for w in raw:
        w = str(w).strip().lower()
        if w:
            result.append(w)

    return result[:20]


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/generate", methods=["POST"])
def generate():

    api_key = os.environ.get("DEEPSEEK_API_KEY")

    if not api_key:
        return jsonify(
            error="服务器未配置 DEEPSEEK_API_KEY"
        ), 500


    data = request.get_json(silent=True) or {}

    words = _parse_words(
        data.get("words", [])
    )

    style = data.get(
        "style",
        "荒诞脑洞"
    )


    if not words:
        return jsonify(
            error="请输入至少一个英文单词"
        ), 400


    user_prompt = f"""
Story style:
{style}

English words:
{", ".join(words)}

Generate JSON.
"""


    def stream():

        full_content = ""


        try:

            resp = requests.post(
                DEEPSEEK_URL,

                headers={
                    "Authorization":
                    f"Bearer {api_key}",
                    "Content-Type":
                    "application/json"
                },

                json={
                    "model": MODEL,

                    "messages":[
                        {
                            "role":"system",
                            "content":SYSTEM_PROMPT
                        },
                        {
                            "role":"user",
                            "content":user_prompt
                        }
                    ],

                    "temperature":0.95,

                    "stream":True
                },

                stream=True,

                timeout=60
            )


            for line in resp.iter_lines():

                if not line:
                    continue


                line = line.decode("utf-8")


                if not line.startswith("data:"):
                    continue


                payload = line[5:].strip()


                if payload == "[DONE]":
                    break


                chunk = json.loads(payload)


                delta = (
                    chunk
                    .get("choices",[{}])[0]
                    .get("delta",{})
                    .get("content","")
                )


                if delta:

                    full_content += delta

                    yield (
                        "data:"
                        +
                        json.dumps(
                            {
                                "type":"text",
                                "content":delta
                            },
                            ensure_ascii=False
                        )
                        +
                        "\n\n"
                    )


            try:

                start = full_content.find("{")

                result = json.loads(
                    full_content[start:]
                )


                yield (
                    "data:"
                    +
                    json.dumps(
                        {
                            "type":"done",
                            "words":
                            result.get(
                                "words",
                                []
                            )
                        },
                        ensure_ascii=False
                    )
                    +
                    "\n\n"
                )


            except Exception:
                pass


        except Exception as e:

            yield (
                "data:"
                +
                json.dumps(
                    {
                        "type":"error",
                        "message":str(e)
                    },
                    ensure_ascii=False
                )
                +
                "\n\n"
            )


    return Response(
        stream(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control":"no-cache",
            "X-Accel-Buffering":"no"
        }
    )


if __name__ == "__main__":
    app.run(
        debug=True,
        port=5000
    )
