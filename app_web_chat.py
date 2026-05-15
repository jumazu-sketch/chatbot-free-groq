import json
import os
from pathlib import Path
from urllib import error, request

import streamlit as st

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_KEYS_URL = "https://console.groq.com/keys"
DEFAULT_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
AVAILABLE_MODELS = [
    "allam-2-7b",
    "canopylabs/orpheus-arabic-saudi",
    "canopylabs/orpheus-v1-english",
    "groq/compound",
    "groq/compound-mini",
    "llama-3.1-8b-instant",
    "llama-3.3-70b-versatile",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "meta-llama/llama-prompt-guard-2-22m",
    "meta-llama/llama-prompt-guard-2-86m",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "openai/gpt-oss-safeguard-20b",
    "qwen/qwen3-32b",
    "whisper-large-v3",
    "whisper-large-v3-turbo",
]
APP_SETTINGS_DIR = Path(os.getenv("APPDATA", Path.home())) / "TesteSolver"
APP_SETTINGS_FILE = APP_SETTINGS_DIR / "config.json"
SYSTEM_PROMPT = (
    "Voce e um assistente objetivo e didatico. "
    "Responda em portugues de forma clara e curta quando possivel."
)


def load_settings() -> dict:
    if not APP_SETTINGS_FILE.exists():
        return {}

    try:
        return json.loads(APP_SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_settings(settings: dict) -> None:
    APP_SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    APP_SETTINGS_FILE.write_text(
        json.dumps(settings, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def validate_api_key_format(api_key: str) -> bool:
    return bool(api_key) and api_key.startswith("gsk_") and len(api_key) >= 20


def extract_text_from_content(content):
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict):
                text = part.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts).strip()

    return ""


def ask_groq(api_key: str, model: str, messages: list[dict]) -> str:
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "max_completion_tokens": 900,
        "top_p": 1,
        "stream": False,
    }

    api_request = request.Request(
        GROQ_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
        },
        method="POST",
    )

    try:
        with request.urlopen(api_request, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(details)
            details = parsed.get("error", {}).get("message", details)
        except json.JSONDecodeError:
            pass
        raise RuntimeError(f"Groq retornou erro HTTP {exc.code}: {details}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Falha de conexao com a API Groq: {exc.reason}") from exc

    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("A API Groq nao retornou resposta.")

    content = choices[0].get("message", {}).get("content", "")
    answer = extract_text_from_content(content)
    if not answer:
        raise RuntimeError("A API Groq respondeu sem conteudo.")

    return answer


def build_messages(history: list[dict]) -> list[dict]:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    return messages


def init_state() -> None:
    if "settings" not in st.session_state:
        st.session_state.settings = load_settings()

    if "messages" not in st.session_state:
        st.session_state.messages = []


def get_effective_key() -> str:
    typed = st.session_state.get("typed_key", "").strip()
    if typed:
        return typed

    saved = st.session_state.settings.get("api_key", "")
    if isinstance(saved, str):
        return saved.strip()

    return ""


def sidebar_settings() -> tuple[str, str]:
    st.sidebar.title("Configuracao")
    st.sidebar.markdown(f"Criar chave: {GROQ_KEYS_URL}")

    saved_key = st.session_state.settings.get("api_key", "")
    if not isinstance(saved_key, str):
        saved_key = ""

    typed_key = st.sidebar.text_input(
        "API Key da Groq",
        value=saved_key,
        type="password",
        key="typed_key",
        placeholder="gsk_...",
    )

    model = st.sidebar.selectbox(
        "Modelo",
        options=AVAILABLE_MODELS,
        index=AVAILABLE_MODELS.index(DEFAULT_MODEL),
    )

    if st.sidebar.button("Salvar chave"):
        if not validate_api_key_format(typed_key.strip()):
            st.sidebar.error("Chave invalida. Ela normalmente comeca com gsk_.")
        else:
            st.session_state.settings["api_key"] = typed_key.strip()
            try:
                save_settings(st.session_state.settings)
                st.sidebar.success("Chave salva no AppData.")
            except OSError as exc:
                st.sidebar.error(f"Nao foi possivel salvar: {exc}")

    if st.sidebar.button("Limpar conversa"):
        st.session_state.messages = []
        st.rerun()

    return typed_key.strip(), model


def render_chat() -> None:
    for msg in st.session_state.messages:
        role = msg.get("role", "assistant")
        content = msg.get("content", "")
        with st.chat_message(role):
            st.markdown(content)


def main() -> None:
    st.set_page_config(page_title="Chat Groq Simples", page_icon=":speech_balloon:", layout="centered")
    init_state()

    st.title("Chat Groq Simples")
    st.caption("Aplicacao web minima de chat usando sua chave da Groq.")

    typed_key, selected_model = sidebar_settings()

    env_key = os.getenv("GROQ_API_KEY", "").strip()
    effective_key = typed_key or get_effective_key() or env_key

    if not validate_api_key_format(effective_key):
        st.info("Informe e salve uma API key valida para comecar o chat.")

    render_chat()

    user_prompt = st.chat_input("Digite sua pergunta...")
    if not user_prompt:
        return

    st.session_state.messages.append({"role": "user", "content": user_prompt})
    with st.chat_message("user"):
        st.markdown(user_prompt)

    if not validate_api_key_format(effective_key):
        with st.chat_message("assistant"):
            st.error("API key invalida. Salve uma chave da Groq para continuar.")
        st.session_state.messages.append(
            {"role": "assistant", "content": "API key invalida. Configure uma chave valida."}
        )
        return

    with st.chat_message("assistant"):
        with st.spinner("Pensando..."):
            try:
                api_messages = build_messages(st.session_state.messages)
                answer = ask_groq(effective_key, selected_model, api_messages)
            except Exception as exc:
                st.error(str(exc))
                st.session_state.messages.append(
                    {"role": "assistant", "content": f"Erro: {exc}"}
                )
                return

        st.markdown(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})


if __name__ == "__main__":
    main()
