import os
import json
import requests
from flask import Flask, request, render_template, jsonify, Response

app = Flask(__name__, template_folder="templates")

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-chat"

SYSTEM_PROMPT = """你是一个中文冷笑话 / 荒诞小故事生成器。

规则：
1. 用户会给你若干个英文单词（可能少于 5 个）。
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


def _extract_story(buffer, state):
    """从不断增长的 JSON 缓冲中，增量提取已确认的 story 字符串片段。

    state 在多次调用间持久保存。返回本次新增的、可安全展示的 story 文本。
    一旦遇到 story 的闭合引号，停止提取（后面的 words 数组不再发送）。
    """
    out = ""
    n = len(buffer)

    if state["done"]:
        return out

    # 1) 定位 "story" 键（只定位一次）
    if state["key_idx"] is None:
        idx = buffer.find('"story"')
        if idx == -1:
            return out  # 关键词还没到齐，等下一波
        state["key_idx"] = idx

    # 2) 还没进入字符串：跳过 "story"、空白与冒号，找到开引号
    if not state["inside"]:
        i = state["key_idx"] + 7  # "story" 之后
        while i < n and buffer[i] != '"':
            if buffer[i] in ' \t\r\n:':
                i += 1
            else:
                return out  # 出现意外字符，等更多数据
        if i >= n:
            return out
        state["inside"] = True
        state["pos"] = i + 1  # 故事正文起点

    # 3) 读取故事正文，直到遇到闭合引号
    i = state["pos"]
    end = n
    if n > 0 and buffer[n - 1] == '\\':  # 末尾反斜杠可能是转义起点，先按住
        end = n - 1
    while i < end:
        ch = buffer[i]
        if state["escaped"]:
            out += ch
            state["escaped"] = False
        elif ch == '\\':
            state["escaped"] = True
        elif ch == '"':
            state["inside"] = False
            state["done"] = True
            i += 1
            state["pos"] = i
            return out
        else:
            out += ch
        i += 1
        state["pos"] = i
    return out


def _event_stream(api_key, user_prompt):
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.95,
        "response_format": {"type": "json_object"},
        "stream": True,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    try:
        resp = requests.post(
            DEEPSEEK_URL,
            headers=headers,
            json=payload,
            stream=True,
            timeout=30,
        )
    except Exception as e:
        yield json.dumps({"type": "error", "error": f"请求失败：{e}"}, ensure_ascii=False) + "\n"
        return

    if resp.status_code != 200:
        err = resp.text[:200]
        resp.close()
        yield json.dumps({"type": "error", "error": f"DeepSeek 接口错误：{resp.status_code} {err}"}, ensure_ascii=False) + "\n"
        return

    buffer = ""
    state = {"key_idx": None, "inside": False, "escaped": False, "pos": 0, "done": False}
    streamed = ""

    try:
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                continue
            try:
                chunk = json.loads(data)
            except Exception:
                continue
            delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
            if not delta:
                continue
            buffer += delta
            new_text = _extract_story(buffer, state)
            if new_text:
                streamed += new_text
                yield json.dumps({"type": "chunk", "text": new_text}, ensure_ascii=False) + "\n"
    except Exception as e:
        resp.close()
        yield json.dumps({"type": "error", "error": f"流读取错误：{e}"}, ensure_ascii=False) + "\n"
        return
    finally:
        try:
            resp.close()
        except Exception:
            pass

    # 收尾：尝试把完整 buffer 解析成规范 JSON，作为高亮的权威来源
    story_canon = streamed
    words_list = []
    try:
        parsed = json.loads(buffer)
        if parsed.get("story"):
            story_canon = parsed["story"]
        words_list = parsed.get("words", []) or []
    except Exception:
        pass

    yield json.dumps({"type": "meta", "story": story_canon, "words": words_list}, ensure_ascii=False) + "\n"
    yield json.dumps({"type": "done"}, ensure_ascii=False) + "\n"


def _easter_egg_stream():
    """小彩蛋：输入 547CeciliaW 时返回专属祝福，无需 API Key。"""
    msg = "祝吴诗琦天天开心，"
    yield json.dumps({"type": "chunk", "text": msg}, ensure_ascii=False) + "\n"
    yield json.dumps({"type": "meta", "story": msg, "words": []}, ensure_ascii=False) + "\n"
    yield json.dumps({"type": "done"}, ensure_ascii=False) + "\n"


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/generate", methods=["POST", "OPTIONS"])
def generate():
    if request.method == "OPTIONS":
        return ("", 204)

    data = request.get_json(silent=True) or {}
    words = _parse_words(data.get("words", []))

    # 小彩蛋：输入 547CeciliaW 触发专属祝福（无需 API Key）
    if words == ["547ceciliaw"]:
        return Response(_easter_egg_stream(), mimetype="application/x-ndjson")

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        return jsonify(error="服务端未配置 DEEPSEEK_API_KEY，请在 Vercel 环境变量中设置。"), 500

    if not words:
        return jsonify(error="请至少输入 1 个英文单词。"), 400
    style = data.get("style", "荒诞脑洞")

    user_prompt = (
        f"风格要求：{style}\n"
        f"单词（{len(words)} 个）：{', '.join(words)}\n"
        f"请按要求返回 JSON。"
    )

    return Response(
        _event_stream(api_key, user_prompt),
        mimetype="application/x-ndjson",
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
