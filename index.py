import os
import json
import requests
from flask import Flask, request, render_template, jsonify

app = Flask(__name__, template_folder="templates")

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-chat"

SYSTEM_PROMPT = """你是一个中文冷笑话 / 荒诞小故事生成器。

规则：
1. 用户会给你 5 个或更多英文单词。
2. 把每个英文单词翻译成贴切语境、自然流畅的中文词或短语（可以意译，不必是词典第一个义项）。
3. 用这些中文词编一句或两句简短、荒诞、有梗的中文小故事，类似冷笑话，脑洞越大越好，句子要通顺好笑。
4. 每个单词的中文含义都必须用上，且 story 中必须原样出现你在 words 里给出的每个「cn」字符串（这样前端才能高亮）。
5. 只输出一个 JSON 对象，不要有任何额外文字、不要 Markdown 围栏。

JSON 格式：
{"story":"一句话故事","words":[{"word":"英文原词","cn":"你实际使用的中文词"}]}

参考示例（严格对齐这种风格）：
示例A 输入 marriage, against, produce, attention, dull
{"story":"有个婚庆公司专门生产无聊的婚礼，吸引了很多注意力，大家都反对他们。","words":[{"word":"marriage","cn":"婚庆"},{"word":"against","cn":"反对"},{"word":"produce","cn":"生产"},{"word":"attention","cn":"注意力"},{"word":"dull","cn":"无聊的"}]}

示例B 输入 burn, rat, education, row, celebrate
{"story":"有只老鼠烧掉了一排课本，干掉了教育，大家都庆祝。","words":[{"word":"burn","cn":"烧"},{"word":"rat","cn":"老鼠"},{"word":"education","cn":"教育"},{"word":"row","cn":"一排"},{"word":"celebrate","cn":"庆祝"}]}

示例C 输入 cause, situation, bell, dirty, clock
{"story":"上课铃响了，但钟表脏了，这种情况导致提前下课。","words":[{"word":"cause","cn":"导致"},{"word":"situation","cn":"情况"},{"word":"bell","cn":"铃"},{"word":"dirty","cn":"脏了"},{"word":"clock","cn":"钟表"}]}"


"""

def _parse_words(raw):
    if isinstance(raw, str):
        raw = raw.split()
    out = []
    for w in raw:
        w = str(w).strip().lower()
        if w:
            out.append(w)
    return out[:20]


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/generate", methods=["POST", "OPTIONS"])
def generate():
    if request.method == "OPTIONS":
        return ("", 204)

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        return jsonify(error="服务端未配置 DEEPSEEK_API_KEY，请在 Vercel 环境变量中设置。"), 500

    data = request.get_json(silent=True) or {}
    words = _parse_words(data.get("words", []))
    style = data.get("style", "荒诞脑洞")
    if len(words) < 5:
        return jsonify(error="至少需要 5 个英文单词。"), 400

    user_prompt = (
        f"风格要求：{style}\n"
        f"单词（{len(words)} 个）：{', '.join(words)}\n"
        f"请按要求返回 JSON。"
    )

    try:
        resp = requests.post(
            DEEPSEEK_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.95,
                "response_format": {"type": "json_object"},
            },
            timeout=25,
        )
        if resp.status_code != 200:
            return jsonify(error=f"DeepSeek 接口错误：{resp.status_code} {resp.text[:200]}"), 502

        content = resp.json()["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        if not parsed.get("story") or not isinstance(parsed.get("words"), list):
            return jsonify(error="模型返回格式异常，请重试。"), 502
        return jsonify(story=parsed["story"], words=parsed["words"])
    except Exception as e:
        return jsonify(error=f"服务器错误：{e}"), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)
