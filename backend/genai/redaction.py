"""Redact configured secrets at LogRecord creation, before any handler formats them."""
import logging
import os
import re
import threading
import traceback

_lock=threading.Lock()

def redact(value):
    text=str(value)
    for name in ('AI_API_KEY','ANTHROPIC_API_KEY','OPENAI_API_KEY'):
        secret=os.getenv(name)
        if secret:text=text.replace(secret,'[REDACTED]')
    return re.sub(r'(?i)(authorization|x-goog-api-key|x-api-key)([\s\"\x27:=]+)(?:Bearer\s+)?[^\s\"\x27,}]+',r'\1\2[REDACTED]',text)

def install_redaction():
    with _lock:
        previous=logging.getLogRecordFactory()
        if getattr(previous,'_inspection_redaction',False):return
        def factory(*args,**kwargs):
            record=previous(*args,**kwargs)
            # Uvicorn's access formatter reads the original structured argument tuple.
            # Preserve its shape while redacting text values before any handler sees it.
            if record.name == 'uvicorn.access' and isinstance(record.args,tuple) and len(record.args)==5:
                record.msg=redact(record.msg)
                record.args=tuple(redact(value) if isinstance(value,str) else value for value in record.args)
            else:
                record.msg=redact(record.getMessage());record.args=()
            if record.exc_info:
                record.exc_text=redact(''.join(traceback.format_exception(*record.exc_info)))
                record.exc_info=None
            if record.stack_info:record.stack_info=redact(record.stack_info)
            return record
        factory._inspection_redaction=True
        logging.setLogRecordFactory(factory)
