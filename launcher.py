import os
import sys
import webbrowser

def setup_env():
    # Determine paths
    if getattr(sys, 'frozen', False):
        DATA_DIR = os.path.join(os.path.expanduser("~"), ".emotionalAdvisor")
    else:
        DATA_DIR = os.path.dirname(os.path.abspath(__file__))

    os.makedirs(DATA_DIR, exist_ok=True)
    env_path = os.path.join(DATA_DIR, ".env")

    # Check if we need to guide user to setup
    if not os.path.exists(env_path):
        print("="*50)
        print("Initial Setup: Welcome to EmotionalAdvisor!")
        print("Please configure your API keys to get started.")
        print("="*50)
        openai_api_key = input("Enter OPENAI_API_KEY: ").strip()
        weflow_token = input("Enter WEFLOW_TOKEN (optional, press Enter to skip): ").strip()
        
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(f"OPENAI_API_KEY={openai_api_key}\n")
            f.write("OPENAI_API_BASE=https://api.openai.com/v1\n")
            f.write("AGENT_MODEL=gpt-4o\n")
            if weflow_token:
                f.write(f"WEFLOW_TOKEN={weflow_token}\n")
        print(f"\nConfiguration saved to {env_path}\n")
    else:
        # Check if OPENAI_API_KEY is empty
        from dotenv import dotenv_values
        config = dotenv_values(env_path)
        if not config.get("OPENAI_API_KEY"):
            print("="*50)
            print("It looks like your OPENAI_API_KEY is missing.")
            print(f"Please edit {env_path} and add your key.")
            print("="*50)
            openai_api_key = input("Enter OPENAI_API_KEY now (or press Enter to skip): ").strip()
            if openai_api_key:
                with open(env_path, "a", encoding="utf-8") as f:
                    f.write(f"\nOPENAI_API_KEY={openai_api_key}\n")
                print("Key added.\n")

if __name__ == "__main__":
    setup_env()
    
    # Import and run the main app
    from gui_main import main
    main()
