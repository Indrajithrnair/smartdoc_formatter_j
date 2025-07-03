import os
from dotenv import load_dotenv, dotenv_values # Import dotenv_values

# Load environment variables from .env file
# Try project root .env first
project_root_dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
print(f"[config.py] Attempting to load .env from project root: {project_root_dotenv_path}")
print(f"[config.py] Does .env exist at project root path? {os.path.exists(project_root_dotenv_path)}") # Corrected variable name

loaded_from_root = False
if os.path.exists(project_root_dotenv_path):
    # Try to load and OVERRIDE existing env vars if any conflict
    loaded_ok = load_dotenv(project_root_dotenv_path, verbose=True, override=True)
    print(f"[config.py] load_dotenv from project root (override=True) success: {loaded_ok}")
    if loaded_ok:
        loaded_from_root = True

if not loaded_from_root:
    # Fallback to .env next to config.py (smartdoc_agent/.env)
    config_dir_dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
    print(f"[config.py] Attempting to load .env from config dir: {config_dir_dotenv_path}")
    print(f"[config.py] Does .env exist at config dir path? {os.path.exists(config_dir_dotenv_path)}")
    if os.path.exists(config_dir_dotenv_path):
        # Try to load and OVERRIDE existing env vars if any conflict
        loaded_ok = load_dotenv(config_dir_dotenv_path, verbose=True, override=True)
        print(f"[config.py] load_dotenv from config dir (override=True) success: {loaded_ok}")
    else:
        print(f"[config.py] No .env found in project root or config dir. Trying default load_dotenv search (override=True).")
        load_dotenv(verbose=True, override=True) # Final fallback

GROQ_API_KEY = os.getenv("GROQ_API_KEY") # This reflects os.environ after dotenv attempts
print(f"[config.py] Global GROQ_API_KEY (from os.getenv after load attempts): '{GROQ_API_KEY}'")

# You can add other configurations here, for example:
# DEFAULT_MODEL_NAME = "llama3-8b-8192"
# MAX_DOCUMENT_TOKENS = 4000

# Define known dummy/placeholder keys
DUMMY_KEYS = [
    "DUMMY_KEY_PROJECT_ROOT",
    "YOUR_GROQ_API_KEY_HERE",
    "DUMMY_KEY_FOR_TESTING_CLI_FLOW",
    "DUMMY_KEY_DO_NOT_USE_FOR_REAL_CALLS"
]

if not GROQ_API_KEY: # This check is on the os.getenv version
    print("Warning: Global GROQ_API_KEY (from os.getenv) is not found. Check .env and environment variables.")
elif GROQ_API_KEY in DUMMY_KEYS:
    print(f"Warning: Global GROQ_API_KEY (from os.getenv) is a DUMMY/PLACEHOLDER key: '{GROQ_API_KEY}'.")


def get_groq_api_key():
    """
    Returns the Groq API key.
    Prioritizes .env file content over pre-existing environment variables if the pre-existing one is a known dummy.
    """
    # Path to .env at the project root (assuming config.py is in smartdoc_agent/)
    dotenv_path_to_check = os.path.join(os.path.dirname(__file__), '..', '.env')

    key_from_dotenv_file = None
    if os.path.exists(dotenv_path_to_check):
        # Read .env file directly without modifying os.environ
        raw_values = dotenv_values(dotenv_path_to_check)
        key_from_dotenv_file = raw_values.get("GROQ_API_KEY")
        print(f"[config.get_groq_api_key] Key read directly from '{dotenv_path_to_check}': '{key_from_dotenv_file[:10] if key_from_dotenv_file else None}...'")

    key_from_os_env = os.getenv("GROQ_API_KEY")
    print(f"[config.get_groq_api_key] Key from os.getenv: '{key_from_os_env[:10] if key_from_os_env else None}...'")

    # Decision logic:
    # 1. If key from .env file is present and not a dummy, use it.
    if key_from_dotenv_file and key_from_dotenv_file not in DUMMY_KEYS:
        print(f"ℹ️ [config.get_groq_api_key] Using key from .env file (it's not a dummy/placeholder).")
        return key_from_dotenv_file

    # 2. If key from .env file is a dummy/None, but key from os.environ is present and not a dummy, use os.environ.
    #    (This covers case where .env has dummy, but shell has real key)
    if key_from_os_env and key_from_os_env not in DUMMY_KEYS:
        print(f"ℹ️ [config.get_groq_api_key] Using key from os.environ (it's not a dummy/placeholder, and .env key was dummy/None).")
        return key_from_os_env

    # 3. If both are None, or both are dummies, or one is None and other is dummy:
    #    Prefer the .env file's value if it exists, otherwise os.environ's value.
    #    This means if .env has a specific dummy, and os.environ has another dummy, .env dummy is preferred.
    #    If .env is missing, and os.environ has a dummy, that dummy is returned.
    if key_from_dotenv_file is not None: # Covers case where key_from_dotenv_file is a dummy or empty string
        print(f"ℹ️ [config.get_groq_api_key] Fallback: Using key from .env file ('{key_from_dotenv_file}'), which might be dummy/placeholder or empty.")
        return key_from_dotenv_file

    # Final fallback to whatever os.getenv gave (could be None or a dummy from shell)
    print(f"ℹ️ [config.get_groq_api_key] Final fallback: Using key from os.getenv ('{key_from_os_env}'), which might be dummy/placeholder or None.")
    if not key_from_os_env: # If it's None or empty after all this
         raise ValueError("GROQ_API_KEY is not set. Please add it to your .env file or set it as an environment variable.")
    return key_from_os_env
