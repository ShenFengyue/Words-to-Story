import os
import json
import requests

from flask import Flask, request, render_template, jsonify, Response


app = Flask(__name__, template_folder="templates")


DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-chat"


SYSTEM_PROMPT = """
You are an AI Chinese funny story generator for English learners.

Rules:

1. The user provides one or more English words.
2. Translate each English word into a natural Chinese word or phrase.
3. Create a short absurd and memorable Chinese story using all translated meanings.
4. Every "cn" value in the words array MUST appear exactly in the story.
5. If there are only one or two words, freely add characters and background.
6. The story should be funny, imaginative, and easy to remember.
7. Output ONLY valid JSON. No markdown.

Format:

{
 "story":"Chinese story",
 "words":[
   {
    "word":"English word",
    "cn":"Chinese meaning"
   }
 ]
}
"""


def parse_words(raw):
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
            error="Missing DEEPSEEK_API_KEY"
        ), 500


    data = request.get_json(silent=True) or {}

    words = parse_words(
        data.get("words", [])
    )

    style = data.get(
        "style",
        "absurd imagination"
    )


    if len(words) == 0:
        return jsonify(
            error="Please input words"
        ), 400


    user_prompt = f"""
Style:
{style}

Words:
{", ".join(words)}

Generate the JSON story.
"""


    def stream():

        full_text = ""


        try:

            response = requests.post(

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


            for line in response.iter_lines():

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

                    full_text += delta

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

                start = full_text.find("{")

                result = json.loads(
                    full_text[start:]
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
