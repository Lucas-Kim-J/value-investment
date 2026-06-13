from mcp.server.fastmcp import FastMCP
import app as _app

mcp = FastMCP("vi-capture")

@mcp.tool()
def capture_note(user: str, title: str, clean_content: str, situation: str, note_type: str,
                 tags: list[str], concepts: list[dict], source: dict | None = None,
                 insight: str | None = None) -> dict:
    """File a knowledge capture into the user's Notion knowledge base. Returns a receipt."""
    return _app.do_capture(user, {
        "title": title, "clean_content": clean_content, "situation": situation,
        "note_type": note_type, "tags": tags, "concepts": concepts, "source": source, "insight": insight})

if __name__ == "__main__":
    mcp.run()
