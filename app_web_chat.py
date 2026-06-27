import base64
import json
import os
from pathlib import Path
from urllib import error, request

import streamlit as st

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_KEYS_URL = "https://console.groq.com/keys"
DEFAULT_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
DEFAULT_API_KEY = "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"
AVAILABLE_MODELS = [
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "llama-3.2-11b-vision-preview",
    "llama-3.2-90b-vision-preview",
    "llama-3.1-8b-instant",
    "llama-3.3-70b-versatile",
    "allam-2-7b",
    "canopylabs/orpheus-arabic-saudi",
    "canopylabs/orpheus-v1-english",
    "groq/compound",
    "groq/compound-mini",
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


def extract_text_from_file(uploaded_file) -> str:
    filename = uploaded_file.name.lower()
    
    # 1. Arquivos de Texto (.txt)
    if filename.endswith(".txt"):
        return uploaded_file.read().decode("utf-8", errors="replace")
        
    # 2. Arquivos PDF (.pdf)
    elif filename.endswith(".pdf"):
        try:
            import pypdf
            pdf_reader = pypdf.PdfReader(uploaded_file)
            text = ""
            for page in pdf_reader.pages:
                text_page = page.extract_text()
                if text_page:
                    text += text_page + "\n"
            return text
        except ImportError:
            return "Erro: Para ler arquivos PDF, a biblioteca 'pypdf' precisa estar instalada no requirements.txt."
        except Exception as e:
            return f"Erro ao ler PDF: {str(e)}"
            
    # 3. Arquivos CSV (.csv)
    elif filename.endswith(".csv"):
        try:
            import pandas as pd
            df = pd.read_csv(uploaded_file)
            # Retorna a tabela formatada como texto
            return df.to_string(index=False)
        except ImportError:
            return "Erro: Para ler arquivos CSV, a biblioteca 'pandas' precisa estar instalada no requirements.txt."
        except Exception as e:
            return f"Erro ao ler CSV: {str(e)}"
            
    # 4. Arquivos Excel (.xlsx, .xls)
    elif filename.endswith((".xlsx", ".xls")):
        if filename.endswith(".xls"):
            return "Erro: O formato antigo '.xls' não é suportado diretamente. Por favor, salve seu arquivo como '.xlsx' (Excel Moderno) e envie novamente."
        try:
            import pandas as pd
            df = pd.read_excel(uploaded_file)
            # Retorna a tabela formatada como texto
            return df.to_string(index=False)
        except ImportError:
            return "Erro: Para ler arquivos Excel, as bibliotecas 'pandas' e 'openpyxl' precisam estar instaladas no requirements.txt."
        except Exception as e:
            return f"Erro ao ler Excel: {str(e)}"
            
    # 5. Arquivos Word (.docx, .doc)
    elif filename.endswith((".docx", ".doc")):
        if filename.endswith(".doc"):
            return "Erro: O formato antigo '.doc' não é suportado diretamente. Por favor, salve seu arquivo como '.docx' (Word Moderno) e envie novamente."
        try:
            import docx
            doc = docx.Document(uploaded_file)
            full_text = []
            for para in doc.paragraphs:
                full_text.append(para.text)
            return "\n".join(full_text)
        except ImportError:
            return "Erro: Para ler arquivos Word, a biblioteca 'python-docx' precisa estar instalada no requirements.txt."
        except Exception as e:
            return f"Erro ao ler DOCX: {str(e)}"
            
    # 6. Arquivos PowerPoint (.pptx, .ppt)
    elif filename.endswith((".pptx", ".ppt")):
        if filename.endswith(".ppt"):
            return "Erro: O formato antigo '.ppt' não é suportado diretamente. Por favor, salve seu arquivo como '.pptx' (PowerPoint Moderno) e envie novamente."
        try:
            from pptx import Presentation
            prs = Presentation(uploaded_file)
            text_runs = []
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text"):
                        text_runs.append(shape.text)
            return "\n".join(text_runs)
        except ImportError:
            return "Erro: Para ler arquivos PowerPoint, a biblioteca 'python-pptx' precisa estar instalada no requirements.txt."
        except Exception as e:
            return f"Erro ao ler PPTX: {str(e)}"
            
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
    api_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history:
        api_messages.append({
            "role": msg["role"],
            "content": msg["content"]
        })
    return api_messages


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
    if isinstance(saved, str) and saved.strip():
        return saved.strip()

    return DEFAULT_API_KEY


def sidebar_settings() -> tuple[str, str]:
    st.sidebar.title("Configuracao")
    st.sidebar.markdown(f"Criar chave: {GROQ_KEYS_URL}")

    saved_key = st.session_state.settings.get("api_key", "")
    if not isinstance(saved_key, str) or not saved_key:
        saved_key = DEFAULT_API_KEY

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
        display = msg.get("display_content", "")
        with st.chat_message(role):
            if role == "user":
                if isinstance(content, list):
                    for item in content:
                        if item.get("type") == "text":
                            st.markdown(item.get("text"))
                        elif item.get("type") == "image_url":
                            st.image(item.get("image_url", {}).get("url", ""), width=300)
                else:
                    st.markdown(display or content)
            else:
                st.markdown(content)


def main() -> None:
    st.set_page_config(page_title="Mazzucas's LLM", page_icon=":speech_balloon:", layout="centered")
    init_state()

    st.title("Mazzuca´s bot")
    st.caption("Aplicacao web minima de chat usando sua chave da Groq.")

    typed_key, selected_model = sidebar_settings()

    env_key = os.getenv("GROQ_API_KEY", "").strip()
    effective_key = typed_key or get_effective_key() or env_key

    # Upload de Arquivos e Imagens (Suporte completo a documentos de escritório e tabelas)
    uploaded_file = st.file_uploader(
        "Upload de arquivo ou imagem (Clique e aperte Ctrl+V para colar imagens)",
        type=["txt", "pdf", "csv", "xlsx", "xls", "docx", "doc", "pptx", "ppt", "png", "jpg", "jpeg"]
    )

    file_context = ""
    image_base64 = ""
    
    if uploaded_file is not None:
        file_name = uploaded_file.name.lower()
        if file_name.endswith((".png", ".jpg", ".jpeg")):
            bytes_data = uploaded_file.read()
            base64_str = base64.b64encode(bytes_data).decode("utf-8")
            ext = "png" if file_name.endswith(".png") else "jpeg"
            image_base64 = f"data:image/{ext};base64,{base64_str}"
            st.image(uploaded_file, caption="Visualização da imagem carregada", width=150)
        else:
            file_context = extract_text_from_file(uploaded_file)
            if file_context and not file_context.startswith("Erro:"):
                st.success(f"Arquivo '{uploaded_file.name}' carregado e processado com sucesso!")
            elif file_context.startswith("Erro:"):
                st.error(file_context)

    if not validate_api_key_format(effective_key):
        st.info("Informe e salve uma API key valida para comecar o chat.")

    render_chat()

    user_prompt = st.chat_input("Digite sua pergunta...")
    if not user_prompt:
        return

    # Processar o tipo de mensagem a ser salva
    if image_base64:
        is_vision = "vision" in selected_model or "scout" in selected_model
        if not is_vision:
            st.warning("⚠️ O modelo atual pode não aceitar imagens. Escolha um modelo de visão no menu lateral.")
            
        message_content = [
            {"type": "text", "text": user_prompt},
            {"type": "image_url", "image_url": {"url": image_base64}}
        ]
        display_content = user_prompt
    elif file_context and not file_context.startswith("Erro:"):
        # Insere o texto extraído do documento no prompt para alimentar o LLM
        message_content = f"Conteúdo do arquivo '{uploaded_file.name}':\n---\n{file_context}\n---\n\nPergunta do usuário: {user_prompt}"
        display_content = f"📄 Enviei o arquivo *{uploaded_file.name}*\n\n{user_prompt}"
    else:
        message_content = user_prompt
        display_content = user_prompt

    st.session_state.messages.append({
        "role": "user",
        "content": message_content,
        "display_content": display_content
    })
    
    with st.chat_message("user"):
        if isinstance(message_content, list):
            for item in message_content:
                if item["type"] == "text":
                    st.markdown(item["text"])
                elif item["type"] == "image_url":
                    st.image(item["image_url"]["url"], width=300)
        else:
            st.markdown(display_content)

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
