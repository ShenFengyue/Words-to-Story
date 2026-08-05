import os
import json
import time
import base64
import requests
from flask import Flask, request, render_template, jsonify, Response

app = Flask(__name__, template_folder="templates")

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-chat"

SYSTEM_PROMPT = """You are a Chinese absurd joke and short story generator.

Rules:

1. The user will provide several English words (possibly fewer than 5).
2. Translate each English word into a natural and context-appropriate Chinese word or phrase. You may use creative interpretations instead of the first dictionary meaning.
3. Use all translated Chinese words to create a short, absurd, funny Chinese mini-story. The humor should come from unexpected combinations of meanings, clever connections, and creative imagination, not from random nonsense. The story should feel like a cold joke: surprising, memorable, and easy to understand, while keeping the sentence natural and fluent.
4. Every English word must be used. The Chinese meaning of every word must appear exactly in the story. The story MUST contain every "cn" string you provide in the "words" array, because the frontend uses these exact strings for highlighting.
5. Output ONLY one JSON object. Do not include explanations, Markdown fences, or any extra text.

JSON format:

{
  "story": "short Chinese story",
  "words": [
    {
      "word": "original English word",
      "cn": "the exact Chinese word or phrase used in the story"
    }
  ]
}

Examples:

Input:
marriage, against, produce, attention, dull

Output:
{
  "story": "有个婚庆公司专门生产无聊的婚礼，他们一直这样做，因此吸引了很多人的注意力，但大家都反对这家婚庆公司的做法。",
  "words": [
    {"word": "marriage", "cn": "婚庆"},
    {"word": "against", "cn": "反对"},
    {"word": "produce", "cn": "生产"},
    {"word": "attention", "cn": "注意力"},
    {"word": "dull", "cn": "无聊的"}
  ]
}

Input:
burn, rat, education, row, celebrate

Output:
{
  "story": "有一只老鼠不小心烧掉了一排课本，影响到了学生教育，可是班里的所有同学，都站起来庆祝。",
  "words": [
    {"word": "burn", "cn": "烧"},
    {"word": "rat", "cn": "老鼠"},
    {"word": "education", "cn": "教育"},
    {"word": "row", "cn": "一排"},
    {"word": "celebrate", "cn": "庆祝"}
  ]
}

Input:
cause, situation, bell, dirty, clock

Output:
{
  "story": "上课铃响起的瞬间，教室墙上的钟表不知道被谁弄脏了，出现这种状况，导致老师不得不提前下课。",
  "words": [
    {"word": "cause", "cn": "导致"},
    {"word": "situation", "cn": "情况"},
    {"word": "bell", "cn": "铃"},
    {"word": "dirty", "cn": "脏了"},
    {"word": "clock", "cn": "钟表"}
  ]
}

"""

# ===== GitHub 存储配置（服务端，前端永不持有）=====
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO = os.environ.get("GITHUB_REPO")          # 形如 "owner/repo"
GITHUB_PATH = os.environ.get("GITHUB_DATA_PATH", "data/feedback.json")
GITHUB_USERS_PATH = os.environ.get("GITHUB_USERS_PATH", "data/users.json")
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main")
GH_API = "https://api.github.com"
ADMIN_KEY = os.environ.get("ADMIN_KEY")             # 可选；设置后 /admin 需要 ?key=


def _gh_headers():
    h = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "wordstory-app",
    }
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h


def _gh_get_file(path=None):
    """返回 (content_str, sha)；文件不存在返回 (None, None)；其他错误抛异常。"""
    if not GITHUB_REPO or not GITHUB_TOKEN:
        return (None, None)
    url = f"{GH_API}/repos/{GITHUB_REPO}/contents/{path or GITHUB_PATH}"
    r = requests.get(url, headers=_gh_headers(), params={"ref": GITHUB_BRANCH}, timeout=20)
    if r.status_code == 404:
        return (None, None)
    if r.status_code != 200:
        raise RuntimeError(f"读取失败：{r.status_code} {r.text[:200]}")
    data = r.json()
    content = base64.b64decode(data["content"]).decode("utf-8")
    return (content, data.get("sha"))


def _gh_put(content_str, sha, message, path=None):
    body = {
        "message": message,
        "content": base64.b64encode(content_str.encode("utf-8")).decode("ascii"),
        "branch": GITHUB_BRANCH,
    }
    if sha:
        body["sha"] = sha
    url = f"{GH_API}/repos/{GITHUB_REPO}/contents/{path or GITHUB_PATH}"
    return requests.put(url, headers=_gh_headers(), json=body, timeout=20)


def save_records(arr, sha=None):
    """写回整个记录数组；遇到 409（sha 过期）自动重试；返回最新 sha。"""
    if not GITHUB_REPO or not GITHUB_TOKEN:
        raise RuntimeError("未配置 GITHUB_REPO / GITHUB_TOKEN")
    content = json.dumps(arr, ensure_ascii=False, indent=2)
    last_err = None
    for _ in range(4):
        try:
            r = _gh_put(content, sha, "update feedback data")
            if r.status_code in (200, 201):
                return r.json().get("content", {}).get("sha")
            if r.status_code == 409:
                _, sha = _gh_get_file()
                continue
            last_err = f"{r.status_code} {r.text[:200]}"
            break
        except Exception as e:
            last_err = str(e)
            break
    raise RuntimeError(f"保存失败：{last_err}")


def load_records():
    if not GITHUB_REPO or not GITHUB_TOKEN:
        return []
    try:
        content, _ = _gh_get_file()
        if content is None:
            return []
        return json.loads(content)
    except Exception:
        return []


def load_users():
    """返回 uid→name 的 dict。"""
    if not GITHUB_REPO or not GITHUB_TOKEN:
        return {}
    try:
        content, _ = _gh_get_file(GITHUB_USERS_PATH)
        if content is None:
            return {}
        return json.loads(content)
    except Exception:
        return {}


def save_users(users_dict):
    """写回 uid→name 映射到 users.json。"""
    if not GITHUB_REPO or not GITHUB_TOKEN:
        raise RuntimeError("未配置 GITHUB_REPO / GITHUB_TOKEN")
    _, sha = _gh_get_file(GITHUB_USERS_PATH)
    content = json.dumps(users_dict, ensure_ascii=False, indent=2)
    last_err = None
    for _ in range(4):
        try:
            r = _gh_put(content, sha, "update user names", path=GITHUB_USERS_PATH)
            if r.status_code in (200, 201):
                return
            if r.status_code == 409:
                _, sha = _gh_get_file(GITHUB_USERS_PATH)
                continue
            last_err = f"{r.status_code} {r.text[:200]}"
            break
        except Exception as e:
            last_err = str(e)
            break
    raise RuntimeError(f"保存用户名失败：{last_err}")


def upsert_record(rec):
    _, sha = _gh_get_file() if (GITHUB_REPO and GITHUB_TOKEN) else (None, None)
    arr = load_records()
    idx = next((i for i, r in enumerate(arr) if r.get("id") == rec.get("id")), None)
    if idx is not None:
        arr[idx] = rec
    else:
        arr.append(rec)
    return save_records(arr, sha)


def delete_record(rid):
    _, sha = _gh_get_file() if (GITHUB_REPO and GITHUB_TOKEN) else (None, None)
    arr = [r for r in load_records() if r.get("id") != rid]
    return save_records(arr, sha)


def clear_records():
    _, sha = _gh_get_file() if (GITHUB_REPO and GITHUB_TOKEN) else (None, None)
    return save_records([], sha)


def load_features():
    """返回所有 rating=good 且带 feature 的短句列表。"""
    arr = load_records()
    return [r.get("feature") for r in arr if r.get("rating") == "good" and r.get("feature")]


def _generate_feature(api_key, story, words, style):
    """调用 DeepSeek，生成一句'好在哪里'的极简特征（<=35字）。失败返回空串。"""
    cn_words = ", ".join(w.get("cn", "") for w in (words or []))
    prompt = (
        "你是一个中文幽默短篇的评审助手。下面是一段用户很喜欢（“夯”）的中文小故事。\n"
        "请用一句极简中文（不超过 35 字）概括这个故事“好在哪里”——聚焦风格、结构、梗/双关、意外感等手法，不要复述剧情，不要解释。\n"
        "只输出这一句话。\n\n"
        f"风格：{style}\n故事：{story}\n用词：{cn_words}"
    )
    try:
        r = requests.post(
            DEEPSEEK_URL,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": "你输出极简中文评审句，不超过35字，不要任何多余内容。"},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.7,
                "stream": False,
            },
            timeout=30,
        )
        if r.status_code != 200:
            return ""
        out = r.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        return out[:60]
    except Exception:
        return ""


def _admin_key_ok(req):
    if not ADMIN_KEY:
        return True
    if req.args.get("key") == ADMIN_KEY:
        return True
    if req.headers.get("x-admin-key") == ADMIN_KEY:
        return True
    return False


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
    """小彩蛋：输入 吴诗琦 时返回专属祝福，无需 API Key。"""
    msg = "祝吴诗琦、547、Ceciliaw天天开心！（你又来啦？）"
    yield json.dumps({"type": "chunk", "text": msg}, ensure_ascii=False) + "\n"
    yield json.dumps({"type": "meta", "story": msg, "words": []}, ensure_ascii=False) + "\n"
    yield json.dumps({"type": "done"}, ensure_ascii=False) + "\n"


def _easter_egg_shenzhe_stream():
    """小彩蛋：输入 申哲 时返回专属介绍，无需 API Key。"""
    msg = """我是申哲，喜欢探索心理学、AI与科技的交叉领域。

保持好奇，独立思考，享受与有趣的人交流。

人生信条：连接人群，创造价值。"""

    yield json.dumps({"type": "chunk", "text": msg}, ensure_ascii=False) + "\n"
    yield json.dumps({"type": "meta", "story": msg, "words": []}, ensure_ascii=False) + "\n"
    yield json.dumps({"type": "done"}, ensure_ascii=False) + "\n"


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/admin")
def admin():
    if not _admin_key_ok(request):
        return "🔒 需要管理员密钥：访问 /admin?key=你的ADMIN_KEY", 403
    return render_template("admin.html")


@app.route("/api/generate", methods=["POST", "OPTIONS"])
def generate():
    if request.method == "OPTIONS":
        return ("", 204)

    data = request.get_json(silent=True) or {}
    words = _parse_words(data.get("words", []))

    # 小彩蛋：输入 547CeciliaW 触发专属祝福（无需 API Key）
    if words == ["吴诗琦"]:
        return Response(_easter_egg_stream(), mimetype="application/x-ndjson")

    # 小彩蛋：输入 申哲 触发专属问候（无需 API Key）
    if words == ["申哲"]:
        return Response(_easter_egg_shenzhe_stream(), mimetype="application/x-ndjson")

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        return jsonify(error="服务端未配置 DEEPSEEK_API_KEY，请在 Vercel 环境变量中设置。"), 500

    if not words:
        return jsonify(error="请至少输入 1 个英文单词。"), 400
    style = data.get("style", "荒诞脑洞")

    # 注入所有“夯”故事的特征（短句），作为风格参考
    features = load_features()
    user_prompt = (
        f"风格要求：{style}\n"
        f"单词（{len(words)} 个）：{', '.join(words)}\n"
    )
    if features:
        user_prompt += (
            "参考：以下为用户过往评为“夯”的故事所提炼的“好在哪里”特征，"
            "请在本次生成中参考其风格与手法（不要照抄具体句子）：\n- "
            + "\n- ".join(features)
            + "\n"
        )
    user_prompt += "请按要求返回 JSON。"

    return Response(
        _event_stream(api_key, user_prompt),
        mimetype="application/x-ndjson",
    )


@app.route("/api/save", methods=["POST", "OPTIONS"])
def save_story():
    """生成完成后自动保存记录（rating=null），不再只记录被评价的故事。"""
    if request.method == "OPTIONS":
        return ("", 204)

    data = request.get_json(silent=True) or {}
    rid = data.get("id")
    if not rid:
        return jsonify(error="缺少 id"), 400

    rec = {
        "id": rid,
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "words": data.get("words", []),
        "style": data.get("style", "荒诞脑洞"),
        "story": data.get("story", ""),
        "rating": None,
        "feature": "",
        "uid": data.get("uid", ""),
        "name": "",
    }
    # 从服务端 users 映射查名字
    uid = data.get("uid", "")
    if uid:
        users = load_users()
        rec["name"] = users.get(uid, "")
    try:
        upsert_record(rec)
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 200
    return jsonify(ok=True)


@app.route("/api/rate", methods=["POST", "OPTIONS"])
def rate():
    if request.method == "OPTIONS":
        return ("", 204)

    data = request.get_json(silent=True) or {}
    rid = data.get("id")
    rating = data.get("rating")
    if not rid or rating not in ("good", "bad"):
        return jsonify(error="无效评价"), 400

    rec = {
        "id": rid,
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "words": data.get("words", []),
        "style": data.get("style", "荒诞脑洞"),
        "story": data.get("story", ""),
        "rating": rating,
        "feature": "",
        "uid": data.get("uid", ""),
        "name": "",
    }
    # 从服务端 users 映射查名字
    uid = data.get("uid", "")
    if uid:
        users = load_users()
        rec["name"] = users.get(uid, "")

    if rating == "good":
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if api_key:
            rec["feature"] = _generate_feature(api_key, rec["story"], data.get("words", []), rec["style"])

    try:
        upsert_record(rec)
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 200
    return jsonify(ok=True, rating=rating, feature=rec["feature"])


@app.route("/api/admin/list", methods=["GET"])
def admin_list():
    if not _admin_key_ok(request):
        return jsonify(error="forbidden"), 403
    return jsonify(records=load_records(), users=load_users())


@app.route("/api/admin/setname", methods=["POST", "OPTIONS"])
def admin_setname():
    if request.method == "OPTIONS":
        return ("", 204)
    if not _admin_key_ok(request):
        return jsonify(error="forbidden"), 403
    data = request.get_json(silent=True) or {}
    uid = data.get("uid", "").strip()
    name = data.get("name", "").strip()
    if not uid:
        return jsonify(error="缺少 uid"), 400
    try:
        users = load_users()
        if name:
            users[uid] = name
        else:
            users.pop(uid, None)
        save_users(users)
        # 同步更新已有记录中的 name 字段
        arr = load_records()
        changed = False
        for r in arr:
            if r.get("uid") == uid:
                r["name"] = name
                changed = True
        if changed:
            _, sha = _gh_get_file()
            save_records(arr, sha)
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 200
    return jsonify(ok=True)


@app.route("/api/admin/delete", methods=["POST", "OPTIONS"])
def admin_delete():
    if request.method == "OPTIONS":
        return ("", 204)
    if not _admin_key_ok(request):
        return jsonify(error="forbidden"), 403
    rid = (request.get_json(silent=True) or {}).get("id")
    if not rid:
        return jsonify(error="缺少 id"), 400
    try:
        delete_record(rid)
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 200
    return jsonify(ok=True)


@app.route("/api/admin/clear", methods=["POST", "OPTIONS"])
def admin_clear():
    if request.method == "OPTIONS":
        return ("", 204)
    if not _admin_key_ok(request):
        return jsonify(error="forbidden"), 403
    try:
        clear_records()
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 200
    return jsonify(ok=True)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
