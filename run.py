"""
Launcher: run this file from a terminal, VS Code or Spyder (F5).
Then open http://127.0.0.1:8000 in the browser.
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)
