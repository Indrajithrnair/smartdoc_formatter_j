import typer
import os # For potential path manipulations if needed, and getenv
import traceback

# Attempt to set up a path for smartdoc_agent if test_cli.py is in project root
import sys
# Assuming smartdoc_agent is in the same directory or PYTHONPATH is set
# If run from project root, 'smartdoc_agent' should be discoverable.

app = typer.Typer()

@app.command()
def simple_test():
    """A simple test command in test_cli.py"""
    print("🚀 CLI registration in test_cli.py works!")
    print("Attempting to import DocumentFormattingAgent...")
    try:
        # Ensure config runs first if agent depends on its side effects (like .env loading)
        # However, config.py itself is part of smartdoc_agent, so direct import of agent should trigger it.
        print("Importing smartdoc_agent.config first (simulating dependency)...")
        from smartdoc_agent.config import GROQ_API_KEY, get_groq_api_key # To trigger .env load
        print(f"  GROQ_API_KEY from test_cli import: {GROQ_API_KEY}")
        print(f"  get_groq_api_key() from test_cli: {get_groq_api_key()}")

        print("Importing smartdoc_agent.core.agent.DocumentFormattingAgent...")
        from smartdoc_agent.core.agent import DocumentFormattingAgent
        print("✅ Import of DocumentFormattingAgent successful in test_cli.py")

        # Optionally, try to instantiate it
        # print("Attempting to instantiate DocumentFormattingAgent...")
        # agent = DocumentFormattingAgent()
        # print("✅ Instantiation of DocumentFormattingAgent successful.")

    except Exception as e:
        print(f"❌ Import or instantiation failed in test_cli.py: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    # Crucial: Ensure .env is loaded if config.py relies on it being loaded by now
    # config.py in smartdoc_agent should handle its own .env loading.
    # If test_cli.py is in project root, and .env is in project root,
    # python-dotenv's default load_dotenv() might pick it up too if called here.
    # from dotenv import load_dotenv
    # print(f"test_cli.py: current dir {os.getcwd()}")
    # found_env = load_dotenv(verbose=True) # Try loading .env from current dir (project root)
    # print(f"test_cli.py: .env loaded by test_cli? {found_env}. GROQ_API_KEY: {os.getenv('GROQ_API_KEY')}")

    app()
