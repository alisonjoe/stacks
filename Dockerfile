# ========================================
# Stage 1: Builder (Python 3.11 Slim)
# ========================================
FROM python:3.11-slim AS builder

ARG VERSION=unknown
ARG FINGERPRINT=unknown

# Labels
LABEL version=$VERSION
LABEL fingerprint=$FINGERPRINT
LABEL description="Download Manager for Anna's Archive"
LABEL maintainer="Zelest Carlyone"

WORKDIR /opt/stacks

# Install dependencies into /install (distroless compatible layout)
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Copy application files
COPY stacks_server.py .
COPY stacks_downloader.py .
COPY startup.py .
COPY VERSION .
COPY web ./web
COPY files ./files


# ========================================
# Stage 2: Distroless Runtime (Python 3)
# ========================================
FROM gcr.io/distroless/python3-debian12

ARG VERSION=unknown
ARG FINGERPRINT=unknown

# Labels again (distroless keeps its own layer)
LABEL version=$VERSION
LABEL fingerprint=$FINGERPRINT

WORKDIR /opt/stacks

# Set Python path to find installed packages
ENV PYTHONPATH=/usr/local/lib/python3.11/site-packages

# Bring in installed Python packages + your app
COPY --from=builder /install /usr/local
COPY --from=builder /opt/stacks /opt/stacks

EXPOSE 7788

# No shell → must be exec form
# -u flag runs Python in unbuffered mode for immediate output
ENTRYPOINT ["/usr/bin/python3", "-u", "startup.py"]