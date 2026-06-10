FROM docker.io/searxng/searxng:latest

ARG HTTP_PROXY=socks5://192.168.1.159:10808
ARG HTTPS_PROXY=socks5://192.168.1.159:10808

RUN python3 -m ensurepip && \
    python3 -m pip install --no-cache-dir pysocks && \
    python3 -m pip install --no-cache-dir --target=/usr/local/searxng/.venv/lib/python3.14/site-packages/ socksio httpx

ENV HTTP_PROXY=socks5://192.168.1.159:10808
ENV HTTPS_PROXY=socks5://192.168.1.159:10808
ENV http_proxy=socks5://192.168.1.159:10808
ENV https_proxy=socks5://192.168.1.159:10808
