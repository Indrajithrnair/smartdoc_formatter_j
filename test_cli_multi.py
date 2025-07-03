import typer

app = typer.Typer(help="Test CLI for Multi-Command Registration")

@app.command("alpha")
def test_cmd_alpha_func(): # Changed func name to avoid clash if Typer uses func name internally too
    """First test command."""
    typer.echo("Test Command Alpha executed!")

@app.command("beta")
def test_cmd_beta_func(): # Changed func name
    """Second test command."""
    typer.echo("Test Command Beta executed!")

if __name__ == "__main__":
    print("[test_cli_multi.py] Calling app()...")
    app()
    print("[test_cli_multi.py] app() finished.")
