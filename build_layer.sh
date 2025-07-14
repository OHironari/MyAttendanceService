#!/bin/bash

set -e

PROJECT_DIR=$(pwd)
CONTAINER_NAME=pyo3_builder_auto

echo "✅ コンテナ起動中..."
docker run --platform linux/amd64 -it --name $CONTAINER_NAME python:3.12 /bin/bash

echo "✅ ソースコードをコンテナにコピー..."
docker cp "$PROJECT_DIR/." "$CONTAINER_NAME":/build

echo "✅ コンテナ内でビルド開始..."
docker exec -it $CONTAINER_NAME /bin/bash -c "
    apt-get update && \
    apt-get install -y curl build-essential unzip zip && \
    curl https://sh.rustup.rs -sSf | sh -s -- -y && \
    source /root/.cargo/env && \
    pip install maturin && \
    cd /build && \
    maturin build --release && \
    mkdir -p layer/python/lib/python3.13/site-packages && \
    unzip target/wheels/*.whl -d tmp_wheel && \
    cp tmp_wheel/*.so layer/python/lib/python3.13/site-packages/ && \
    cd layer && \
    zip -r /layer.zip python
"

echo "✅ zip ファイルをローカルにコピー..."
docker cp $CONTAINER_NAME:/layer/layer.zip ./layer.zip

echo "✅ コンテナ削除..."
docker rm -f $CONTAINER_NAME

echo "🎉 完了！ローカルに layer.zip が作成されました ✅"
