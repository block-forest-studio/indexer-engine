import asyncio
import typer
from dotenv import load_dotenv
from InquirerPy import inquirer
from indexer_engine.app.interface.tasks import TASKS


load_dotenv()

app = typer.Typer()
indexer_app = typer.Typer(help="cli for indexing on chain data.")
app.add_typer(indexer_app, name="indexer")


@indexer_app.command("run")
def run() -> None:
    task_name = inquirer.select(
        message="Select task:",
        choices=list(TASKS.keys()),
        pointer="❯",
        instruction="Use ↑/↓ to move, Enter to select",
    ).execute()
    chain_id = int(
        inquirer.text(
            message="Chain ID (e.g. 1 for Ethereum mainnet):",
            default="1",
        ).execute()
    )
    from_block = inquirer.text(
        message="From block (inclusive):",
        default="earliest",
    ).execute()
    to_block = inquirer.text(
        message="To block (inclusive):",
        default="latest",
    ).execute()

    asyncio.run(
        TASKS[task_name](
            chain_id=chain_id,  # type: ignore
            from_block=from_block,  # type: ignore
            to_block=to_block,  # type: ignore
        )
    )


if __name__ == "__main__":
    LOGO = r"""

    /$$$$$$$  /$$                     /$$       /$$$$$$$$                                        /$$
    | $$__  $$| $$                    | $$      | $$_____/                                       | $$
    | $$  \ $$| $$  /$$$$$$   /$$$$$$$| $$   /$$| $$     /$$$$$$   /$$$$$$   /$$$$$$   /$$$$$$$ /$$$$$$
    | $$$$$$$ | $$ /$$__  $$ /$$_____/| $$  /$$/| $$$$$ /$$__  $$ /$$__  $$ /$$__  $$ /$$_____/|_  $$_/
    | $$__  $$| $$| $$  \ $$| $$      | $$$$$$/ | $$__/| $$  \ $$| $$  \__/| $$$$$$$$|  $$$$$$   | $$
    | $$  \ $$| $$| $$  | $$| $$      | $$_  $$ | $$   | $$  | $$| $$      | $$_____/ \____  $$  | $$ /$$
    | $$$$$$$/| $$|  $$$$$$/|  $$$$$$$| $$ \  $$| $$   |  $$$$$$/| $$      |  $$$$$$$ /$$$$$$$/  |  $$$$/
    |_______/ |__/ \______/  \_______/|__/  \__/|__/    \______/ |__/       \_______/|_______/    \___/

    Tailor-made Web3 tools studio

      --- Indexer Engine CLI ---
    """
    typer.echo(LOGO)
    app()
