import os
import sys
import traceback


DEFAULT_OPENAI_API_BASE = "https://api.openai.com/v1"
DEFAULT_MODEL_NAME = "gpt-4o"
DEFAULT_TEMPERATURE = "0.7"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_DB_PERSIST_PATH = "./db"
DEFAULT_WECHAT_SYNC_URL = "http://127.0.0.1:5031/api/v1/push/messages"


def _prompt_value(prompt: str, default: str = "", allow_empty: bool = False) -> str:
    while True:
        suffix = f" [{default}]" if default else ""
        value = input(f"{prompt}{suffix}: ").strip()
        if value:
            return value
        if default:
            return default
        if allow_empty:
            return ""
        print("This field cannot be empty.")


def _normalize_config(config: dict) -> dict:
    normalized = dict(config)
    if not normalized.get("MODEL_NAME") and normalized.get("AGENT_MODEL"):
        normalized["MODEL_NAME"] = normalized["AGENT_MODEL"]
    return normalized


def _write_env_file(env_path: str, config: dict):
    config = _normalize_config(config)
    lines = [
        "# ==========================================",
        "# Core LLM Configuration",
        "# ==========================================",
        f"OPENAI_API_KEY={config.get('OPENAI_API_KEY', '')}",
        f"OPENAI_API_BASE={config.get('OPENAI_API_BASE', DEFAULT_OPENAI_API_BASE)}",
        f"MODEL_NAME={config.get('MODEL_NAME', DEFAULT_MODEL_NAME)}",
        f"TEMPERATURE={config.get('TEMPERATURE', DEFAULT_TEMPERATURE)}",
        "",
        "# ==========================================",
        "# Skill-specific Models",
        "# ==========================================",
        f"SIMP_MODEL={config.get('SIMP_MODEL', '')}",
        f"NUWA_MODEL={config.get('NUWA_MODEL', '')}",
        f"BAZI_MODEL={config.get('BAZI_MODEL', '')}",
        "",
        "# ==========================================",
        "# RAG & Storage",
        "# ==========================================",
        f"EMBEDDING_MODEL={config.get('EMBEDDING_MODEL', DEFAULT_EMBEDDING_MODEL)}",
        f"DB_PERSIST_PATH={config.get('DB_PERSIST_PATH', DEFAULT_DB_PERSIST_PATH)}",
        "",
        "# ==========================================",
        "# WeChat Sync",
        "# ==========================================",
        f"WECHAT_SYNC_URL={config.get('WECHAT_SYNC_URL', DEFAULT_WECHAT_SYNC_URL)}",
        f"WECHAT_SYNC_TOKEN={config.get('WECHAT_SYNC_TOKEN', '')}",
    ]

    with open(env_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def _collect_all_config(existing: dict | None = None) -> dict:
    existing = _normalize_config(existing or {})

    print("=" * 50)
    print("Core LLM Configuration")
    print("=" * 50)
    config = {
        "OPENAI_API_KEY": _prompt_value(
            "Enter OPENAI_API_KEY",
            existing.get("OPENAI_API_KEY", ""),
        ),
        "OPENAI_API_BASE": _prompt_value(
            "Enter OPENAI_API_BASE",
            existing.get("OPENAI_API_BASE", DEFAULT_OPENAI_API_BASE),
        ),
        "MODEL_NAME": _prompt_value(
            "Enter MODEL_NAME",
            existing.get("MODEL_NAME", DEFAULT_MODEL_NAME),
        ),
        "TEMPERATURE": _prompt_value(
            "Enter TEMPERATURE",
            existing.get("TEMPERATURE", DEFAULT_TEMPERATURE),
        ),
    }

    print("\n" + "=" * 50)
    print("Skill-specific Models")
    print("Press Enter to inherit MODEL_NAME for optional fields.")
    print("=" * 50)
    config["SIMP_MODEL"] = _prompt_value(
        "Enter SIMP_MODEL",
        existing.get("SIMP_MODEL", ""),
        allow_empty=True,
    )
    config["NUWA_MODEL"] = _prompt_value(
        "Enter NUWA_MODEL",
        existing.get("NUWA_MODEL", ""),
        allow_empty=True,
    )
    config["BAZI_MODEL"] = _prompt_value(
        "Enter BAZI_MODEL",
        existing.get("BAZI_MODEL", ""),
        allow_empty=True,
    )

    print("\n" + "=" * 50)
    print("RAG & Storage")
    print("=" * 50)
    config["EMBEDDING_MODEL"] = _prompt_value(
        "Enter EMBEDDING_MODEL",
        existing.get("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL),
    )
    config["DB_PERSIST_PATH"] = _prompt_value(
        "Enter DB_PERSIST_PATH",
        existing.get("DB_PERSIST_PATH", DEFAULT_DB_PERSIST_PATH),
    )

    print("\n" + "=" * 50)
    print("WeChat Sync")
    print("If you do not use WeChat Sync, you can leave the token blank.")
    print("=" * 50)
    config["WECHAT_SYNC_URL"] = _prompt_value(
        "Enter WECHAT_SYNC_URL",
        existing.get("WECHAT_SYNC_URL", DEFAULT_WECHAT_SYNC_URL),
    )
    config["WECHAT_SYNC_TOKEN"] = _prompt_value(
        "Enter WECHAT_SYNC_TOKEN",
        existing.get("WECHAT_SYNC_TOKEN", ""),
        allow_empty=True,
    )

    return config


def setup_env():
    # Determine paths
    if getattr(sys, "frozen", False):
        data_dir = os.path.join(os.path.expanduser("~"), ".emotionalAdvisor")
    else:
        data_dir = os.path.dirname(os.path.abspath(__file__))

    os.makedirs(data_dir, exist_ok=True)
    env_path = os.path.join(data_dir, ".env")

    from dotenv import dotenv_values

    if not os.path.exists(env_path):
        print("=" * 50)
        print("Initial Setup: Welcome to EmotionalAdvisor!")
        print("Please complete the full .env configuration.")
        print("=" * 50)
        config = _collect_all_config()
        _write_env_file(env_path, config)
        print(f"\nConfiguration saved to {env_path}\n")
        return

    config = _normalize_config(dotenv_values(env_path))
    required_keys = [
        "OPENAI_API_KEY",
        "OPENAI_API_BASE",
        "MODEL_NAME",
        "TEMPERATURE",
        "SIMP_MODEL",
        "NUWA_MODEL",
        "BAZI_MODEL",
        "EMBEDDING_MODEL",
        "DB_PERSIST_PATH",
        "WECHAT_SYNC_URL",
        "WECHAT_SYNC_TOKEN",
    ]
    missing_keys = [key for key in required_keys if key not in config]

    if missing_keys:
        print("=" * 50)
        print("Your .env is missing some fields.")
        print("Please complete the full configuration now.")
        print("=" * 50)
        config = _collect_all_config(config)
        _write_env_file(env_path, config)
        print(f"Updated configuration saved to {env_path}\n")

if __name__ == "__main__":
    setup_env()
    try:
        # Import and run the main app
        from gui_main import main
        main()
    except Exception:
        print("\n[!] Application failed to start:\n")
        traceback.print_exc()
        if getattr(sys, "frozen", False):
            input("\nPress Enter to exit...")
        raise
