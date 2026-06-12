FROM continuumio/miniconda3:latest

WORKDIR /app

# Cria o ambiente conda dedicado (Python 3.9, exigido pelo pyActigraphy)
RUN conda create -n pyActi39 python=3.9 -y && conda clean -afy

SHELL ["conda", "run", "--no-capture-output", "-n", "pyActi39", "/bin/bash", "-c"]

# numba precisa ser instalado antes do pyActigraphy nesta versão
RUN python -m pip install --no-cache-dir numba==0.57.1 \
    && python -m pip install --no-cache-dir pyActigraphy==1.2.2

COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

ENTRYPOINT ["conda", "run", "--no-capture-output", "-n", "pyActi39", \
            "streamlit", "run", "app.py", \
            "--server.address=0.0.0.0", "--server.port=8501"]
