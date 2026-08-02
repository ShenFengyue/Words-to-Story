import os
import json
import requests

from flask import (
    Flask,
    request,
    render_template,
    jsonify,
    Response
)


app = Flask(
    __name__,
    template_folder="templates"
)


DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"

MODEL = "deepseek-chat"


SYSTEM_PROMPT = """
You are a Chinese absurd cold joke and funny story generator.

Your task:

1. The user will provide any number of English words (1 or more).
2. Translate each English word into a natural Chinese word or phrase.
   The translation does not need to be the dictionary first meaning.
   Choose the meaning that works best in the story.
3. Create a short, funny, absurd Chinese story using ALL translated Chinese meanings.
4. The story should be imaginative, weird, and humorous, similar to a Chinese cold joke.
5. Every "cn" value in the words array MUST appear exactly in the story text.
   This is required because the frontend will highlight these words.
6. If the user provides only a few words, freely add characters, scenes, and events to make the story complete.
7. If the user provides many words, try to naturally include all of them.
8. Return ONLY a valid JSON object.
9. Do not use Markdown.
10. Do not add explanations.

Required JSON format:

{
  "story": "Chinese funny story",
  "words": [
    {
      "word": "original English word",
      "cn": "Chinese meaning used in story"
    }
  ]
}

Example:

Input:
dog apple

Output:

{
  "story":"一只狗发现了苹果，于是成立了一个专门保护苹果的公司。",
  "words":[
    {
      "word":"dog",
      "cn":"狗"
    },
    {
      "word":"apple",
      "cn":"苹果"
    }
  ]
}
"""


def _parse_words(raw):

    if isinstance(raw, str):
        raw = raw.split()

    result = []

    for word in raw:

        word = str(word).strip().lower()

        if word:
            result.append(word)

    # avoid too many tokens
    return result[:20]



@app.route("/")
def home():

    return render_template(
        "index.html"
    )



@app.route(
    "/api/generate",
    methods=["POST"]
)
def generate():

    api_key = os.environ.get(
        "DEEPSEEK_API_KEY"
    )


    if not api_key:

        return jsonify(
            error="Missing DEEPSEEK_API_KEY"
        ),500



    data = request.get_json(
        silent=True
    ) or {}


    words = _parse_words(
        data.get(
            "words",
            []
        )
    )


    style = data.get(
        "style",
        "absurd imagination"
    )


    if len(words) == 0:

        return jsonify(
            error="Please input at least one English word."
        ),400



    user_prompt = f"""
Style:
{style}

English words:
{", ".join(words)}

Generate the JSON result according to the rules.
"""


    def generate_stream():

        try:

            response = requests.post(

                DEEPSEEK_URL,

                headers={

                    "Content-Type":
                    "application/json",

                    "Authorization":
                    f"Bearer {api_key}"

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


            if response.status_code != 200:

                yield (
                    "data:"
                    + json.dumps(
                        {
                            "error":
                            response.text
                        },
                        ensure_ascii=False
                    )
                    +
                    "\n\n"
                )

                return



            for line in response.iter_lines():

                if not line:
                    continue


                decoded = line.decode(
                    "utf-8"
                )


                if not decoded.startswith(
                    "data:"
                ):
                    continue


                content = decoded[5:].strip()


                if content == "[DONE]":
                    break



                try:

                    chunk = json.loads(
                        content
                    )


                    delta = (
                        chunk
                        .get("choices",[{}])[0]
                        .get("delta",{})
                        .get("content","")
                    )


                    if delta:

                        yield (
                            "data:"
                            +
                            json.dumps(
                                {
                                    "content":delta
                                },
                                ensure_ascii=False
                            )
                            +
                            "\n\n"
                        )


                except Exception:

                    continue



        except Exception as e:


            yield (
                "data:"
                +
                json.dumps(
                    {
                        "error":str(e)
                    },
                    ensure_ascii=False
                )
                +
                "\n\n"
            )



    return Response(

        generate_stream(),

        mimetype="text/event-stream",

        headers={

            "Cache-Control":
            "no-cache",

            "X-Accel-Buffering":
            "no"

        }

    )




if __name__ == "__main__":

    app.run(
        debug=True,
        port=5000
    )
