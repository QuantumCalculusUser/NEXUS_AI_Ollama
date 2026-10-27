from __future__ import annotations
import threading
from PySide6.QtCore import QThread, Signal
from .ollama_client import OllamaClient, OllamaError
from .internet import check_internet, search_web
from .local_context import context_for_request

class ChatWorker(QThread):
    token=Signal(str); finished_text=Signal(str); failed=Signal(str)
    def __init__(self,host,model,messages,parent=None):
        super().__init__(parent); self.host=host; self.model=model; self.messages=messages; self.cancel_event=threading.Event()
    def cancel(self): self.cancel_event.set()
    def run(self):
        try:
            client=OllamaClient(self.host,timeout=15)
            result=client.chat_stream(self.model,self.messages,self.token.emit,stop_event=self.cancel_event)
            self.finished_text.emit(result)
        except Exception as exc: self.failed.emit(str(exc))

class PullWorker(QThread):
    progress=Signal(str,int,int); finished_pull=Signal(str); failed=Signal(str)
    def __init__(self,host,model,parent=None): super().__init__(parent); self.host=host; self.model=model
    def run(self):
        try:
            def update(event):
                total=int(event.get('total') or 0); done=int(event.get('completed') or 0)
                pct=int(done*100/total) if total else 0
                self.progress.emit(event.get('status','Downloading model'),pct,done)
            OllamaClient(self.host,timeout=15).pull_model(self.model,update)
            self.finished_pull.emit(self.model)
        except Exception as exc: self.failed.emit(str(exc))


class ConnectionWorker(QThread):
    """Check local Ollama and external internet without freezing the GUI."""
    checked = Signal(bool, str, bool, str)
    def __init__(self, host, parent=None):
        super().__init__(parent); self.host=host
    def run(self):
        ollama_ok, ollama_message = OllamaClient(self.host, timeout=2).health()
        internet = check_internet(timeout=3)
        self.checked.emit(ollama_ok, ollama_message, internet.online, internet.detail)


class WebSearchWorker(QThread):
    results = Signal(list); failed = Signal(str)
    def __init__(self, query, parent=None):
        super().__init__(parent); self.query=query
    def run(self):
        try: self.results.emit(search_web(self.query))
        except Exception as exc: self.failed.emit(str(exc))


class ChatContextWorker(QThread):
    """Gather only the local/web context relevant to a single user message."""
    ready = Signal(str, list); failed = Signal(str)
    def __init__(self, query, search_web_enabled, local_inspection_enabled, parent=None):
        super().__init__(parent)
        self.query=query
        self.search_web_enabled=search_web_enabled
        self.local_inspection_enabled=local_inspection_enabled
    def run(self):
        sections=[]
        results=[]
        if self.local_inspection_enabled:
            try:
                local = context_for_request(self.query)
                if local:
                    sections.append(local)
            except Exception as exc:
                sections.append(f'[LOCAL CONTEXT ERROR]\n{exc}')
        if self.search_web_enabled and should_search_web(self.query):
            try:
                results=search_web(self.query)
                if results:
                    lines=[]
                    for item in results:
                        snippet=f" — {item.get('snippet', '')}" if item.get('snippet') else ''
                        lines.append(f"- {item['title']}: {item['url']}{snippet}")
                    sections.append('[LIVE WEB SEARCH RESULTS]\n' + '\n'.join(lines))
                else:
                    sections.append('[LIVE WEB SEARCH RESULTS]\nNo results were returned.')
            except Exception as exc:
                sections.append(f'[LIVE WEB SEARCH ERROR]\n{exc}')
        self.ready.emit('\n\n'.join(sections), results)


def should_search_web(query: str) -> bool:
    """Auto-search only when the user makes an explicit online-research request."""
    text = query.casefold()
    phrases = ('search online', 'search the web', 'search web', 'look up', 'lookup', 'browse', 'find online', 'on the internet')
    return any(phrase in text for phrase in phrases) or ('online' in text and 'search' in text) or 'web search' in text
