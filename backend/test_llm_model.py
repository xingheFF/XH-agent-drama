"""
LLM 模型诊断脚本 — 零依赖，直接用 Python 内置库发请求。

用法（在云服务器上）：
    cd backend
    python3 test_llm_model.py
"""
import json
import os
import sys
import urllib.request
import urllib.error


def parse_env():
    """用纯 Python 读取 .env 文件。"""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(env_path):
        print("⚠️ 没找到 .env 文件:", env_path)
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                if value and value not in os.environ:
                    os.environ[key] = value


def main():
    parse_env()

    base_url = os.getenv("API91_BASE_URL", "").strip()
    api_key = os.getenv("API91_API_KEY", "").strip()
    model_name = os.getenv("LLM_MODEL_NAME", "gpt-5.6-terra").strip()
    provider = os.getenv("LLM_PROVIDER", "ark").strip().lower()

    # 如果配置的是 ark，用 ark 的 URL 和 key
    if provider == "ark":
        base_url = os.getenv("VOLCENGINE_ARK_API_BASE_URL", "").strip()
        api_key = os.getenv("VOLCENGINE_ARK_API_KEY", "").strip()

    if not base_url or not api_key:
        print("❌ 错误：API base_url 或 api_key 为空！请检查 .env 文件。")
        print(f"   LLM_PROVIDER = {provider}")
        print(f"   base_url = {base_url or '(空)'}")
        print(f"   api_key = {'(已设置)' if api_key else '(空)'}")
        return

    url = f"{base_url.rstrip('/')}/v1/chat/completions"
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": "你是一个测试助手。"},
            {"role": "user", "content": "回复一个字：好"},
        ],
        "max_tokens": 10,
        "temperature": 0.1,
    }

    print("=" * 60)
    print("LLM 模型诊断")
    print("=" * 60)
    print(f"  API 服务商 (LLM_PROVIDER): {provider}")
    print(f"  API base_url:             {base_url}")
    print(f"  .env 中 LLM_MODEL_NAME:   {model_name}")
    print(f"  实际发送的 model 字段:     {model_name}")
    print(f"  请求 URL:                 {url}")
    print("=" * 60)
    print()
    print("⏳ 正在发送请求...")

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            resp_text = resp.read().decode("utf-8")
            data = json.loads(resp_text)

            print()
            print("=" * 60)
            print("✅ 请求成功！API 返回内容：")
            print("=" * 60)
            print(f"  请求发送的 model:   {model_name}")
            print(f"  API 返回的 model:   {data.get('model', '(无)')}")

            resp_model = data.get("model", "")
            if resp_model and resp_model != model_name:
                print()
                print("  ⚠️⚠️⚠️ 模型名不一致！⚠️⚠️⚠️")
                print(f"  你发送的是:   {model_name}")
                print(f"  API 返回的是: {resp_model}")
                print("  这说明 API 服务商在后端做了模型别名映射！")
                print("  你的代码没有问题，问题在 API 服务商的配置上。")
                print("  解决方法：登录你的 API 服务商后台，检查模型映射配置。")
            elif resp_model == model_name:
                print()
                print("  ✅ 模型名一致，API 服务商没有做别名映射。")
            else:
                print()
                print("  ⚠️ API 没有返回 model 字段，无法判断。")

            print()
            print("-" * 60)
            print("完整 API 响应（前 1000 字符）：")
            print("-" * 60)
            print(json.dumps(data, ensure_ascii=False, indent=2)[:1000])

    except urllib.error.HTTPError as exc:
        resp_text = exc.read().decode("utf-8", errors="replace")
        print()
        print("❌ API 返回 HTTP 错误：")
        print(f"  状态码: {exc.code}")
        print(f"  响应体: {resp_text[:1000]}")
    except Exception as exc:
        print()
        print(f"❌ 请求失败: {type(exc).__name__}: {exc}")

    print()
    print("=" * 60)
    print("诊断完成。")
    print("=" * 60)


if __name__ == "__main__":
    main()
