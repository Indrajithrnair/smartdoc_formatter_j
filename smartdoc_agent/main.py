import typer
from typing import Annotated, Optional
import os
import traceback # For detailed error printing

print("[main.py] Starting imports...")

try:
    from smartdoc_agent.core.agent import DocumentFormattingAgent
    print("✅ [main.py] Successfully imported DocumentFormattingAgent")
except Exception as e:
    print(f"❌ [main.py] Failed to import DocumentFormattingAgent: {e}")
    traceback.print_exc()
    DocumentFormattingAgent = None

try:
    from smartdoc_agent.config import GROQ_API_KEY
    print(f"✅ [main.py] Successfully imported GROQ_API_KEY from config. Value: '{GROQ_API_KEY}'")
except Exception as e:
    print(f"❌ [main.py] Failed to import GROQ_API_KEY from config: {e}")
    traceback.print_exc()
    GROQ_API_KEY = None

app = typer.Typer(help="Smart Document Formatting Agent CLI")

@app.command() # Typer will make this callable as 'format-document'
def format_document(
    doc_path: Annotated[str, typer.Option("--doc-path", help="Path to the .docx file to format.")],
    query: Annotated[str, typer.Option("--query", help="Your formatting request (e.g., 'Make this document professional').")],
    output_path: Annotated[Optional[str], typer.Option("--output-path", help="Path to save the formatted document.")] = None,
):
    """
    Analyzes and formats a .docx document based on your query.
    """
    print(f"[main.py] CMD format_document called. GROQ_API_KEY at this point: '{GROQ_API_KEY}'")
    if not os.path.exists(doc_path):
        typer.secho(f"Error: Document not found at '{doc_path}'", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    loaded_groq_key_in_command = os.getenv("GROQ_API_KEY")
    if not loaded_groq_key_in_command or loaded_groq_key_in_command == "YOUR_GROQ_API_KEY_HERE":
        typer.secho("GROQ_API_KEY is not set or is the default placeholder. Please set a valid key or the DUMMY_KEY in your .env file at the project root.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    elif "DUMMY" in loaded_groq_key_in_command.upper():
        typer.secho(f"Warning: Using DUMMY_KEY ('{loaded_groq_key_in_command}') for GROQ. LLM-dependent features will not work correctly.", fg=typer.colors.YELLOW)

    actual_output_path = output_path
    if actual_output_path is None:
        base, ext = os.path.splitext(doc_path)
        actual_output_path = f"{base}_formatted{ext}"

    typer.echo(f"Starting document formatting for: {doc_path}")
    typer.echo(f"User query: '{query}'")
    typer.echo(f"Output will be saved to: {actual_output_path}")

    if DocumentFormattingAgent is None:
        typer.secho("Critical Error: DocumentFormattingAgent class failed to import (is None). Cannot proceed.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    try:
        agent = DocumentFormattingAgent()
        result = agent.run(
            user_query=query,
            document_path=doc_path,
            output_document_path=actual_output_path
        )

        typer.secho("\n--- Agent Processing Complete ---", fg=typer.colors.GREEN)
        typer.echo("Agent's final response:")
        typer.echo(result)

        if os.path.exists(actual_output_path):
            typer.secho(f"\nFormatted document saved to: {actual_output_path}", fg=typer.colors.CYAN)
        else:
            typer.secho(f"\nNote: Output document was expected at '{actual_output_path}' but was not found.", fg=typer.colors.YELLOW)

    except ValueError as ve:
        typer.secho(f"Configuration or Value Error during agent operation: {ve}", fg=typer.colors.RED)
        if "Groq API key not found" in str(ve) or "API key" in str(ve).lower() :
             typer.echo("Please ensure your GROQ_API_KEY is correctly set in .env at the project root.")
    except Exception as e:
        typer.secho(f"An unexpected error occurred during agent operation: {e}", fg=typer.colors.RED)
        traceback.print_exc()


@app.command() # Typer will make this callable as 'check-config'
def check_config():
    """Checks if the configuration (like API keys) is loaded correctly."""
    typer.echo("Checking configuration...")
    loaded_key = os.getenv("GROQ_API_KEY")
    if loaded_key and loaded_key not in ["YOUR_GROQ_API_KEY_HERE", "DUMMY_KEY_PROJECT_ROOT", "DUMMY_KEY_FOR_TESTING_CLI_FLOW", "DUMMY_KEY_DO_NOT_USE_FOR_REAL_CALLS"]:
        typer.secho(f"GROQ API Key is loaded: '{loaded_key}'", fg=typer.colors.GREEN)
    elif loaded_key and "DUMMY" in loaded_key.upper():
        typer.secho(f"GROQ API Key is a DUMMY_KEY ('{loaded_key}'). LLM features will not work as expected.", fg=typer.colors.YELLOW)
    elif loaded_key == "YOUR_GROQ_API_KEY_HERE":
        typer.secho("GROQ API Key is loaded but is the placeholder. Please update .env at the project root.", fg=typer.colors.YELLOW)
    else:
        typer.secho("GROQ API Key NOT FOUND in environment. Check .env at project root.", fg=typer.colors.RED)

if __name__ == "__main__":
    print("[main.py] Calling app() for multi-command app (full)...")
    app()
    print("[main.py] app() call finished.")
