FROM searxng/searxng:latest

USER root

RUN python3 -m ensurepip && \
    python3 -m pip install --no-cache-dir \
      --target=/usr/local/searxng/.venv/lib/python3.14/site-packages/ \
      socksio

USER searxng